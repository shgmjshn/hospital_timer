"""実ブラウザで確かめる画面挙動。

Django のテストクライアントでは確かめられないもの（実際の描画サイズ、条件表示の
JavaScript、リロードなしの更新、通知許可）だけをここに置く。
"""

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

# 実在の鍵ではないが、ブラウザ側の base64url デコードを通せる形式のダミー
E2E_VAPID_PUBLIC_KEY = (
    "BMkknwz4lwQ6F3dIFcWVvU1SgJ8AWLo-Rj8jVlwwAK5E6xyuP-juZI3CFmd6VucueUI56f0mDXk0oN95BJCM4I4"
)

# ヘッドレスの Chromium は通知許可の状態を常に denied と報告し、未決定を表現できない。
# 「まだ決めていない」状態だけをここで作り、許可を求める処理そのものは本物を通す。
UNDECIDED_PERMISSION_STUB = """
Object.defineProperty(Notification, "permission", {get: () => "default", configurable: true});
"""

# ブラウザ本体のプッシュサービスへの接続だけを差し替える。
# 許可の取得から購読情報の送信・保存までは本物の経路を通す。
PUSH_SERVICE_STUB = """
navigator.serviceWorker.register = async () => ({
  pushManager: {
    subscribe: async () => ({
      toJSON: () => ({
        endpoint: "https://push.example.test/e2e-subscription",
        keys: {p256dh: "e2e-p256dh", auth: "e2e-auth"},
      }),
    }),
  },
});
"""


def test_status_view_is_readable_without_login_or_registration(
    page, live_server, make_entry, masters, clinic_hours
):
    """一時識別リンクを開くだけで、ログインも文字入力もなく待ち時間が読める。"""
    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    page.goto(f"{live_server.url}/s/{second.pk}/")

    wait_text = page.locator("[data-status-wait-text]")
    expect(wait_text).to_have_text(re.compile(r"^約\d+分$"))
    assert page.url.endswith(f"/s/{second.pk}/"), "ログイン画面へ飛ばされてはならない"
    assert page.locator("input[type=text], input[type=search], textarea").count() == 0

    # 実際に描画されたサイズで可読性を確かめる（設定値ではなく結果を見る）
    body_px = font_size_of(page, "body")
    wait_px = font_size_of(page, "[data-status-wait-text]")
    assert body_px >= 16
    assert wait_px >= 2 * body_px


def test_free_text_and_reservation_time_appear_only_when_needed(
    page, live_server, masters, clinic_hours
):
    """自由記述欄は症状選択後、予約時刻欄は予約を選んだときだけ現れる。"""
    page.goto(f"{live_server.url}/intake/")

    free_text = page.locator('[data-reveal-when="symptom"]')
    reserved_at = page.locator('[data-reveal-when="visit_type=reserved"]')
    expect(free_text).to_be_hidden()
    expect(reserved_at).to_be_hidden()

    page.select_option("#id_symptom", value=str(masters.fever.pk))
    expect(free_text).to_be_visible()
    expect(reserved_at).to_be_hidden()

    page.check('input[name="visit_type"][value="reserved"]')
    expect(reserved_at).to_be_visible()

    page.check('input[name="visit_type"][value="walk_in"]')
    expect(reserved_at).to_be_hidden()
    expect(free_text).to_be_visible()


def test_wait_time_is_reflected_without_reloading(
    page, live_server, make_entry, masters, clinic_hours
):
    """診察完了の記録が、リロードなしで待っている人の画面に反映される。"""
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)

    page.goto(f"{live_server.url}/s/{second.pk}/")
    expect(page.locator("[data-status-wait-text]")).to_have_text("約10分")

    start_exam(head)
    finish_exam()

    # 確定呼出（イベントB）が画面内表示へフォールバックして届く
    notice = page.locator("[data-status-notice]")
    expect(notice).to_contain_text("診察室にお入りください", timeout=15_000)
    expect(page.locator("[data-status-wait]")).to_be_hidden()


def test_notification_permission_is_offered_on_the_status_view(
    page, live_server, make_entry, masters, clinic_hours, settings
):
    """通知の許可がまだのときは、許可を求める案内を出す。"""
    settings.VAPID_PUBLIC_KEY = E2E_VAPID_PUBLIC_KEY
    entry = make_entry(masters.fever)

    page.add_init_script(UNDECIDED_PERMISSION_STUB)
    page.goto(f"{live_server.url}/s/{entry.pk}/")

    prompt = page.locator("[data-push-permission-prompt]")
    expect(prompt).to_be_visible()
    expect(prompt.locator("[data-push-permission-button]")).to_be_enabled()


def test_notification_prompt_is_not_shown_without_vapid_keys(
    page, live_server, make_entry, masters, clinic_hours, settings
):
    """Web Push を送れない構成では許可を求めない（画面内表示にフォールバックする）。"""
    settings.VAPID_PUBLIC_KEY = ""
    entry = make_entry(masters.fever)

    page.add_init_script(UNDECIDED_PERMISSION_STUB)
    page.goto(f"{live_server.url}/s/{entry.pk}/")

    expect(page.locator("[data-status-notice]")).to_be_visible()
    expect(page.locator("[data-push-permission-prompt]")).to_be_hidden()


def test_granting_notification_permission_registers_a_subscription(
    page, context, live_server, make_entry, masters, clinic_hours, settings, wait_until
):
    """通知を許可すると、その端末の届け先が保存され、案内は消える。"""
    from notifier.models import PushSubscription

    settings.VAPID_PUBLIC_KEY = E2E_VAPID_PUBLIC_KEY
    entry = make_entry(masters.fever)

    context.grant_permissions(["notifications"], origin=live_server.url)
    page.add_init_script(UNDECIDED_PERMISSION_STUB)
    page.add_init_script(PUSH_SERVICE_STUB)
    page.goto(f"{live_server.url}/s/{entry.pk}/")

    page.click("[data-push-permission-button]")

    assert wait_until(lambda: PushSubscription.objects.filter(entry=entry).exists()), (
        "通知許可後に購読が保存されていない"
    )
    subscription = PushSubscription.objects.get(entry=entry)
    assert subscription.endpoint == "https://push.example.test/e2e-subscription"
    expect(page.locator("[data-push-permission-prompt]")).to_be_hidden()


def font_size_of(page, selector):
    size = page.evaluate(
        "selector => getComputedStyle(document.querySelector(selector)).fontSize", selector
    )
    return float(size.removesuffix("px"))
