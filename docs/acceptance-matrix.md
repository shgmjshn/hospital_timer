# 受入テスト対応表と実装契約

## 1. 要件 ⇔ テスト対応表

| 要件 | テスト |
| --- | --- |
| 1. Intake Form | `tests/test_intake_form.py` |
| 2. Queue Store（並び順・Duration Table） | `tests/test_queue_store.py` |
| 3. Wait-Time Engine | `tests/test_wait_time_engine.py` |
| 4. Status View | `tests/test_status_view.py` |
| 5. Notifier | `tests/test_notifier.py` |
| 6. 医師の閲覧 | `tests/test_doctor_access.py` |
| エッジケース（閉院・待ち時間ゼロ・未登録症状） | `tests/test_edge_cases.py` |
| セキュリティ制約 | `tests/test_security.py` |
| 技術スタック・構成要素の命名 | `tests/test_project_structure.py` |
| 実ブラウザでしか確かめられない画面挙動 | `tests/e2e/test_patient_flow.py`（`pytest -m e2e`） |

### 仕様が明示した合否判定

| 判定項目 | テスト |
| --- | --- |
| Status View の URL を Cookie/キャッシュなしで開くと、ログインを経ずに到達する | `test_status_view.py::test_reachable_without_login_registration_or_cookies` |
| 空の必須項目では提出不可 | `test_intake_form.py::test_empty_required_field_is_rejected`（6 項目をパラメータ化） |
| 自由記述が空でも提出成功 | `test_intake_form.py::test_submission_succeeds_with_empty_free_text` |
| 待ち時間文字列が `^約[0-9]+分$` に一致 | `test_wait_time_engine.py::test_wait_text_matches_the_required_format`、`test_status_view.py::test_state_json_wait_text_matches_the_required_format` |
| 範囲表現・「約」なしを禁止 | `test_wait_time_engine.py::test_wait_text_never_uses_a_range_or_omits_the_prefix` |
| 診察完了記録がない間、通知送信件数は 0 | `test_notifier.py::test_no_notification_is_sent_before_a_completion_is_recorded` |
| 非医師リクエストでは症状・自由記述が返らない | `test_doctor_access.py::test_anonymous_request_does_not_return_clinical_data`、`::test_authenticated_non_doctor_does_not_return_clinical_data`、`::test_patient_status_view_never_exposes_clinical_data` |

### 追加確定分の合否判定

| 判定項目 | テスト |
| --- | --- |
| イベントA: 待ち時間 0 到達で「まもなくお呼びします」を表示 | `test_wait_time_engine.py::test_head_of_queue_gets_the_come_to_room_message_instead_of_zero_minutes`、`test_notifier.py::test_event_a_appears_when_the_patient_reaches_the_head_of_the_queue` |
| イベントA は通知を送らない（画面表示のみ） | `test_notifier.py::test_event_a_is_shown_without_sending_any_push` |
| イベントB: 完了記録で先頭の 1 人にのみ確定呼出 | `test_notifier.py::test_completion_sends_exactly_one_final_call_to_the_next_patient`、`::test_final_call_is_not_duplicated_for_the_same_patient` |
| 診察中フラグ true の間は送らない | `test_notifier.py::test_no_final_call_while_the_doctor_is_in_exam` |
| 予約者は予約時刻順（提出順ではない） | `test_queue_store.py::test_reserved_patients_are_ordered_by_reservation_time_not_submission` |
| 予約者は飛び込みより優先 | `test_queue_store.py::test_reserved_patients_are_placed_before_walk_ins` |
| 最小所要時間 1 分 | `test_queue_store.py::test_duration_below_one_minute_is_clamped_on_save`、`::test_duration_below_one_minute_is_clamped_on_create`、`::test_measured_value_below_one_minute_is_clamped` |
| リンク寿命: 診察終了後は「診察は終了しました」 | `test_status_view.py::test_finished_entry_shows_the_finished_message` |
| 通知フォールバック: 未許可なら画面内表示 | `test_notifier.py::test_final_call_falls_back_to_in_page_display_when_push_is_not_permitted` |
| 予約来院は予約時刻の入力が必須 | `test_intake_form.py::test_reserved_visit_requires_reservation_time` |
| 翌日以降の予約は待ち時間ではなく予約日時を表示 | `test_status_view.py::test_future_reservation_shows_the_reservation_time_instead_of_a_wait_time` |
| 未登録症状アラートを管理画面で確認できる | `test_edge_cases.py::test_unregistered_symptom_alert_is_visible_in_the_admin` |

## 2. 実装契約

テストが前提としている名前とふるまい。実装時はこの契約に合わせる。

### queue_store.models

| 名前 | 内容 |
| --- | --- |
| `Symptom` | `code` / `name` / `display_order` / `is_active` |
| `SymptomDuration` | `symptom`（OneToOne、`related_name="duration"`）/ `duration_minutes` / `sample_count`。`save()` は `MIN_DURATION_MINUTES` 未満を切り上げ、`full_clean()` は `ValidationError`。`record_actual(minutes)` は移動平均で更新し `sample_count` を増やす |
| `AgeBand` | `label` / `display_order` / `is_active` |
| `Gender` | `code` / `label` / `display_order` / `is_active` |
| `QueueEntry` | `id`（UUIDField 主キー、既定値 `uuid4`）/ `full_name`※ / `kana`※ / `age_band` / `gender` / `symptom` / `free_text`※ / `visit_type`（`VisitType.RESERVED` `WALK_IN`）/ `reserved_at` / `submitted_at`（既定値 `timezone.now`）/ `status`（`Status.WAITING` `IN_EXAM` `DONE`）/ `exam_started_at` / `finished_at`。※はアプリ層で暗号化 |
| `ClinicSchedule` | `weekday`(0=月) / `is_closed` / `open_time` / `close_time` / `break_start` / `break_end` |
| `ClinicClosure` | `date` / `reason` |
| `ConsultationRoomState` | 単一レコード。`load()` で取得。`is_in_exam` / `current_entry` |
| `UnregisteredSymptomAlert` | `symptom` / `entry` / `applied_minutes` / `acknowledged`。管理画面の一覧に症状名を表示する |

### queue_store のサービス

- `queue_store.ordering.waiting_queue(now=None)`: 当日分のみ、`WAITING` と `IN_EXAM` を対象に
  「予約者（`reserved_at` 昇順）→ 飛び込み（`submitted_at` 昇順）」の順で返す。
- `queue_store.hours.is_reception_open(now=None)`: 営業時間内かつ昼休み外かつ休診日でないとき `True`。
- `queue_store.hours.next_open_at(now=None)`: 次回受付開始時刻。
- `queue_store.services.start_exam(entry)`: `IN_EXAM` にし診察中フラグを `True` にする。
- `queue_store.services.finish_exam(entry=None)`: `DONE` にして待機列から外し、診察中フラグを
  `False` にしてから Notifier のイベントBを起動する。

### wait_time_engine.engine

- `Phase`: `WAITING` `COME_TO_ROOM` `IN_EXAM` `FINISHED` `CLOSED` `SCHEDULED_FUTURE` `QUEUE_EMPTY`
  （JSON では `"waiting"` などの文字列値）
- `format_minutes(minutes) -> "約N分"`
- `duration_minutes_for(symptom, entry=None) -> int`: Duration Table に無ければ
  `DEFAULT_DURATION_MINUTES` を返し `UnregisteredSymptomAlert` を記録する
- `wait_minutes_for(entry, now=None) -> int`: 自分より前のエントリの所要時間合計
- `status_for(entry, now=None)`: `phase` / `wait_text` / `message` / `position`
- `overall_status(now=None)`: `phase` / `wait_text` / `message` / `waiting_count`

表示の優先順位は `FINISHED` → `SCHEDULED_FUTURE` → `CLOSED` → 確定呼出 → `COME_TO_ROOM` → `WAITING`。
`COME_TO_ROOM` と `QUEUE_EMPTY` と `CLOSED` では `wait_text` を `None` にする（「約0分」を出さない）。

### URL 名とレスポンス

| URL 名 | パス | 備考 |
| --- | --- | --- |
| `intake:form` | `/intake/` | GET で入力画面、POST で登録。成功時は `status_view:detail` へ 302。受付停止中は 403 |
| `status_view:lobby` | `/` | 待合室向けの総合表示 |
| `status_view:detail` | `/s/<uuid>/` | 患者向け単一画面 |
| `status_view:state` | `/s/<uuid>/state.json` | ポーリング用 |
| `notifier:subscribe` | Web Push の購読登録 | JSON で `endpoint` と `keys.p256dh` `keys.auth` を受ける |
| `doctor_console:queue` | `/doctor/` | 医師ロールのみ |
| `doctor_console:entry_detail` | `/doctor/entry/<uuid>/` | 症状・自由記述を表示。非医師は 403 |
| `doctor_console:start_exam` | `/doctor/entry/<uuid>/start/` | POST |
| `doctor_console:finish_exam` | `/doctor/entry/<uuid>/finish/` | POST |

`state.json` のキー: `phase` / `wait_text` / `message` / `position` / `waiting_count` /
`poll_interval_seconds` / `final_call`。症状と自由記述は含めない。

### テンプレートに必要な目印

| 目印 | 用途 |
| --- | --- |
| `--body-font-size: Npx` / `--wait-font-size: Npx` | 可読性の数値基準（本文 16px 以上、待ち時間はその 2 倍以上） |
| `data-poll-interval="N"` | ポーリング間隔の宣言 |
| `data-push-permission-prompt` | 通知許可を求める要素 |
| `data-reveal-when="symptom"` | 症状選択後に表示する自由記述欄（初期状態は `hidden`） |
| `data-reveal-when="visit_type=reserved"` | 予約選択時に表示する予約時刻欄（初期状態は `hidden`） |
| `name="viewport"` | 拡大操作なしで読めるレイアウト |

Status View と `state.json` のレスポンスヘッダには `Cache-Control: no-store` と
`X-Robots-Tag: noindex` を付ける。

### notifier

- `PushSubscription`: `entry` / `endpoint` / `p256dh` / `auth`
- `NotificationLog`: `entry` / `kind`（`Kind.FINAL_CALL`）/ `channel`（`Channel.WEB_PUSH`
  `Channel.IN_PAGE`）/ `status`
- `transport.WebPushTransport`: 実送信。`transport.MemoryTransport`: テスト用。
  `sent` は `{"endpoint": str, "payload": dict}` のリストで、`reset()` で空にする。
  使用するクラスは `settings.NOTIFIER_PUSH_TRANSPORT` で切り替える
- `dispatcher.dispatch_final_call()`: 診察中フラグが `True` のとき、または先頭患者に
  既に確定呼出済みのときは `None` を返す。送信できたら `NotificationLog` を返す

### 表示文言

| 場面 | 文言 |
| --- | --- |
| 閉院・受付停止 | 「本日の受付は終了しました」＋次回受付時刻 |
| 待機列が空（総合表示） | 「お待ちの方はいません」「すぐにご案内できます」 |
| イベントA（待ち時間 0 到達） | 「まもなくお呼びします。診察室の前にお越しください」 |
| イベントB（確定呼出） | 「診察室にお入りください」を含む文言 |
| 診察終了後 | 「診察は終了しました」 |

### config/settings_production.py

`DEBUG = False`、`SECURE_SSL_REDIRECT = True`、`SESSION_COOKIE_SECURE = True`、
`CSRF_COOKIE_SECURE = True`、`SECURE_HSTS_SECONDS >= 31536000`。
