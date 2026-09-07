# Render へのデプロイ（学習用・無料枠）

GitHub に push したあと、ダッシュボードの操作だけで公開 URL が付く。
無料の Web は 15 分アクセスが無いと眠り、次のアクセスで約 1 分かかる。
無料 Postgres は作成から 30 日で期限切れ（その後 14 日で削除）。患者の本番データには使わない。

## 1. 手元で鍵を作る

仮想環境を有効にして実行する。

```bash
source .venv/bin/activate
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

表示された 1 行が `FIELD_ENCRYPTION_KEY`。これを Render に貼る。
紛失すると保存済みの氏名・フリガナ・自由記述が復号できなくなる。

管理者のユーザー名とパスワードも決めておく（例: `admin` と自分だけが知る値）。

## 2. Blueprint で作る

1. [Render Dashboard](https://dashboard.render.com) に GitHub でログインする。
2. **New** → **Blueprint** を選び、このリポジトリを選ぶ。
3. `render.yaml` が読まれる。未入力の環境変数を入れる。

| 変数 | 入れるもの |
| --- | --- |
| `FIELD_ENCRYPTION_KEY` | 上で作った Fernet 鍵 |
| `DJANGO_SUPERUSER_USERNAME` | 管理者のユーザー名 |
| `DJANGO_SUPERUSER_PASSWORD` | 管理者のパスワード |

`DJANGO_SECRET_KEY` と `DATABASE_URL` は Render が埋める。
`DJANGO_SETTINGS_MODULE` は `config.settings_production` のままにする。

4. **Apply** してデプロイ完了を待つ（初回は数分）。

## 3. 公開 URL

デプロイ後のホスト名は `https://hospital-timer.onrender.com` のような形になる
（名前が衝突していれば末尾に番号が付く）。

| 画面 | パス |
| --- | --- |
| 待合室 | `/` |
| 問診票 | `/intake/` |
| 医師・管理（同じユーザー） | `/doctor/` と `/admin/` |

問診票の QR には `https://（ホスト）/intake/` を載せる。

最初のアクセスは休眠からの起動で待たされることがある。

## 4. Blueprint を使わない場合

1. **New** → **Postgres** → プラン **Free**。
2. **New** → **Web Service** → この GitHub リポジトリ。
   - Runtime: Python
   - Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start: `bash bin/render-start.sh`
   - Instance: **Free**
3. Environment に次を入れる。
   - `DJANGO_SETTINGS_MODULE` = `config.settings_production`
   - `DATABASE_URL` = Postgres の Internal Database URL（Add from で Postgres を選ぶ）
   - `DJANGO_SECRET_KEY` = Generate
   - `FIELD_ENCRYPTION_KEY` / `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD`

## 5. デプロイ後に確認すること

- `/intake/` が開ける（受付時間内であること。土曜 13:00 以降と日曜は既定では閉まる）。
- `/doctor/` に作った管理者でログインできる。
- 問診票を 1 件出して、待ち時間画面に進む。

無料枠にシェルはない。ユーザーの追加は環境変数を変えて再デプロイするか、
管理画面 `/admin/` から行う。

## 6. 更新の出し方

GitHub の既定ブランチへ push すると、Render が自動でビルドして差し替える。
マイグレーションとマスタ投入は起動のたびに走る（何度実行しても同じ結果）。
