# 待ち時間確認システム（地域医療クリニック向け）

Python + Django + PostgreSQL による待ち時間確認システム。患者は UUID v4 の一時識別リンクから
ログインなしに自分の待ち時間だけを確認でき、症状と自由記述は医師ロールのみが閲覧できる。

## 現在の状態

構成要素（Intake Form / Queue Store / Wait-Time Engine / Status View / Notifier / 医師の閲覧）は
すべて実装済みで、受入テスト 87 件が合格する。

実装が満たすべきモデル・サービス・URL の契約は [docs/acceptance-matrix.md](docs/acceptance-matrix.md)
に一覧化してある。

## 画面と URL

| URL | 内容 | 権限 |
| --- | --- | --- |
| `/intake/` | 問診票。受付時間外は 403 で提出不可 | 誰でも |
| `/s/<uuid>/` | 患者向けの単一画面（一時識別リンク） | 誰でも・ログイン不要 |
| `/s/<uuid>/state.json` | 上記のポーリング用。症状と自由記述は含めない | 誰でも |
| `/` | 待合室モニタ向けの総合表示 | 誰でも |
| `/doctor/` | 待機列一覧と診察開始・完了の記録 | 医師ロール |
| `/doctor/entry/<uuid>/` | 症状と自由記述の閲覧 | 医師ロール |
| `/admin/` | マスタと未登録症状アラート、通知記録 | 管理者 |

## 構成

| ディレクトリ | 役割 |
| --- | --- |
| `config/` | 設定・URLconf・WSGI |
| `queue_store/` | 待機列、Duration Table、営業時間、診察中フラグ、未登録症状アラート |
| `intake/` | Intake Form（問診票） |
| `wait_time_engine/` | 待ち時間の算出と表示文字列の生成 |
| `status_view/` | 患者向け単一画面と状態 JSON |
| `notifier/` | Web Push の購読管理と確定呼出のディスパッチ |
| `doctor_console/` | 医師ロール専用の待機列閲覧・診察開始/完了の記録 |
| `tests/` | 受入テスト |

## セットアップ

### 1. 依存関係

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. PostgreSQL

Docker Compose で起動する。

```bash
docker compose up -d db
docker compose exec db pg_isready -U hospital_timer
```

ホスト側のポートは **55432**（コンテナ内は 5432）。5432 は他プロジェクトの PostgreSQL と
衝突しやすいため既定値をずらしてある。変更する場合は `POSTGRES_HOST_PORT` を指定する。

```bash
POSTGRES_HOST_PORT=5432 docker compose up -d db
```

既存の PostgreSQL を使う場合は、以下の環境変数で接続先を指定する。

```bash
export POSTGRES_DB=hospital_timer
export POSTGRES_USER=hospital_timer
export POSTGRES_PASSWORD=hospital_timer
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=55432
```

テスト用データベース（`test_hospital_timer`）を作るため、接続ユーザーには `CREATEDB` 権限が必要。

### 3. 環境変数

開発用の既定値は `config/settings.py` に埋め込んであるため、ローカルでは設定なしで動く。
本番では以下を必ず環境変数で与える。

| 変数 | 用途 |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django のシークレットキー |
| `FIELD_ENCRYPTION_KEY` | 氏名・フリガナ・自由記述のフィールド暗号化キー（Fernet） |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIM_EMAIL` | Web Push |
| `POSTGRES_*` | データベース接続 |

`FIELD_ENCRYPTION_KEY` の生成:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

VAPID 鍵（Web Push）の生成:

```bash
python - <<'EOF'
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01, b64urlencode

vapid = Vapid01()
vapid.generate_keys()
print("VAPID_PUBLIC_KEY=", b64urlencode(vapid.public_key.public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)), sep="")
print("VAPID_PRIVATE_KEY=", b64urlencode(
    vapid.private_key.private_numbers().private_value.to_bytes(32, "big")), sep="")
EOF
```

`VAPID_PUBLIC_KEY` が未設定のときは通知許可を求めず、確定呼出は Status View の画面内表示に
フォールバックする。

### 4. マイグレーションと初期マスタ

```bash
python manage.py migrate
python manage.py seed_masters      # 年齢帯・性別・症状・所要時間・営業時間
python manage.py createsuperuser
```

医師ロールは `doctors` グループ（`settings.DOCTOR_GROUP_NAME`）で表す。管理画面で作成し、
医師ユーザーを所属させる。

### 5. ローカル HTTPS で起動

Web Push とサービスワーカーは安全なオリジンでしか動かないため、HTTPS で起動する。

```bash
mkcert -install && mkcert localhost 127.0.0.1     # 初回のみ
python manage.py runserver_plus --cert-file localhost+1.pem --key-file localhost+1-key.pem 0.0.0.0:8443
```

mkcert を使わない場合は自己署名証明書でも起動できる。

```bash
python manage.py runserver_plus --cert-file /tmp/hospital-timer.crt
```

## テストの実行

```bash
source .venv/bin/activate
pytest                      # 全件（87 件）。E2E は除外される
pytest tests/test_intake_form.py            # 要件1のみ
pytest -k reserved                          # 予約関連のみ
pytest tests/test_project_structure.py      # DB不要（技術スタックと構成の検証）
```

### E2E（Playwright）

実ブラウザが必要なため既定では走らせない。初回のみブラウザを取得する。

```bash
playwright install chromium
pytest -m e2e               # 6 件
pytest -m e2e --headed --slowmo 300         # 動きを目で追う
```

WSL2 では Playwright 同梱の Chromium が起動直後に落ちることがある。E2E は既定で
システムの Google Chrome を使う。別のブラウザに切り替える場合は
`pytest -m e2e --browser-channel chromium`。

テストは `pytest-django` で実行し、DB は毎回 `test_hospital_timer` を作成・破棄する。
再利用して高速化する場合は `pytest --reuse-db`。

時刻に依存する判定は `freezegun` で 2026-09-02(水) 10:00 JST に固定している。
閉院・昼休みなど別の時刻を使うテストは、その中で `freeze_time` を入れ替える。

## テストの方針

- 主観的な要件は数値基準に置き換えて検証する。
  - 「10 秒以内に反映」→ ポーリング間隔を設定値化し、上限秒数以下であることと再計算の即時反映を検証。
  - 「拡大操作なしに読める」→ 本文 16px 以上、待ち時間の数字はその 2 倍以上であることを検証。
- 実装モジュールはテスト関数の内部で遅延インポートしている。未実装の段階でもテストの収集が
  成立し、失敗理由が個々のテストに現れるようにするため。
- ブラウザ実機でしか確かめられない挙動だけを `tests/e2e/` に置く。実際に描画された文字サイズ、
  症状選択後の自由記述欄の出現、リロードなしの更新、通知許可から購読登録までの流れの 4 種類。
- E2E では時刻を固定しない。freezegun は `time.monotonic` まで止めるため Playwright の
  タイムアウト計測が壊れる。代わりに終日開院の営業時間と実時刻の待機列を使う。
- 通知許可の状態（未決定）とプッシュサービスへの接続だけは、ヘッドレスの Chromium が
  表現できないため差し替える。許可の要求・購読情報の送信・保存は本物の経路を通している。
