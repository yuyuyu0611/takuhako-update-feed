# takuhako-update-feed

卓ハコ（販売版・体験版）の **安定版更新情報** を配信するためだけの公開リポジトリです。
アプリの更新確認は、このリポジトリを GitHub Pages で公開した次の URL を読みます。

```
https://yuyuyu0611.github.io/takuhako-update-feed/update.json
```

- 卓ハコ本体のソースコード、配布 ZIP/EXE、利用者データ、認証情報はここに置きません。
- 個人版は更新確認を行いません。`personal` の情報は登録しません（登録するとアプリは JSON 全体を拒否します）。
- 新しい版の配布は BOOTH の公式商品ページだけで行います。ここから配布物は出しません。
  - 公式商品ページ（販売版・体験版共通）: https://yuaso-syuttyou.booth.pm/items/8709668
- BOOTH のページ・ファイル名・フォルダ名から版番号を自動で読み取ることはしません。
  **版番号はこの `update.json` を管理者が手で書き換えたものだけが正** です。
- 自動公開の仕組み（GitHub Actions 等）は使っていません。`main` ブランチの内容がそのまま公開されます。

## ファイル

| ファイル | 役割 |
|---|---|
| `update.json` | 公開する更新情報。アプリが読むのはこれだけです |
| `.nojekyll` | GitHub Pages の Jekyll 変換を止め、ファイルをそのまま配信させる（空ファイル） |
| `.gitattributes` | JSON 等を LF 改行で保存する |
| `tools/check_feed.py` | 公開前の形式チェックと、公開 URL の取得チェック（Python 3.8 以上、標準ライブラリのみ） |

## update.json の書き方

何も通知しない状態（初期状態）:

```json
{
  "schema": "takuhako-update-feed/1",
  "app_id": "takuhako",
  "channel": "stable",
  "editions": {}
}
```

版を載せた状態の形（`<...>` はすべて実際の値に置き換えます。このままでは検査に通りません）:

```json
{
  "schema": "takuhako-update-feed/1",
  "app_id": "takuhako",
  "channel": "stable",
  "editions": {
    "commercial": {
      "version": "<BOOTHで公開した版 例 1.4.2>",
      "published": true,
      "published_at": "<BOOTHで公開した日時(UTC) 例 2026-01-15T11:00:00Z>",
      "booth_url": "https://yuaso-syuttyou.booth.pm/items/8709668",
      "summary": "<一行の概要>",
      "release_notes": "<変更点の説明>"
    },
    "trial": {
      "version": "<体験版としてBOOTHで公開した版>",
      "published": true,
      "published_at": "<体験版の公開日時(UTC)>",
      "booth_url": "https://yuaso-syuttyou.booth.pm/items/8709668",
      "summary": "<一行の概要>",
      "release_notes": "<変更点の説明>"
    }
  }
}
```

| 項目 | 決まり |
|---|---|
| `schema` / `app_id` / `channel` | 上の値から変えない |
| `editions` | `commercial`（販売版）と `trial`（体験版）だけ。片方だけでもよい。**`personal` は書かない** |
| `version` | 半角の `数字.数字.数字`（例 `1.4.2`）。`v1.4.2`・`1.4.2-rc1`・`01.4.2` は不可 |
| `published` | `true` で通知対象、`false` で通知しない。引用符を付けない |
| `published_at` | BOOTH で実際に公開した日時を **UTC** で `YYYY-MM-DDTHH:MM:SSZ`。日本時間から 9 時間引く（例 日本時間 1月15日 20:00 → `2026-01-15T11:00:00Z`）。未来の日時だとその時刻まで通知されません |
| `booth_url` | 公式商品ページ URL と **完全一致**。`?` 以降や `#` を付けない。末尾 `/` も付けない |
| `summary` | 500 文字以内のプレーンテキスト |
| `release_notes` | 2000 文字以内のプレーンテキスト（改行は `\n`） |

そのほかの決まり: 上の表にないキーを足さない／同じキーを 2 回書かない／数値を書かない（版番号も日時も文字列）／
UTF-8（BOM なし）で保存／ファイル全体 64KiB 以下。どれかに違反すると、アプリは JSON 全体または該当 edition を採用せず、通知は出ません。

販売版と体験版は **それぞれ独立に** 判定されます。片方の entry をもう片方の代わりに使うことはありません。

## 新しい版を公開する手順

順番を守ってください。**BOOTH で実際に配布できる状態を確かめるまで `published` を `true` にしません。**

1. **BOOTH へアップロード**
   新しい版の配布ファイルを BOOTH の公式商品ページへアップロードし、公開状態にする。
2. **実際にダウンロードして確認**
   購入者として（体験版は無料配布として）実際にダウンロードし、展開・起動して、
   アプリの「バージョン情報」が公開する版番号と一致することを確認する。販売版・体験版を別々に確認する。
3. **`update.json` を編集**
   公開した edition の `version`・`published_at`（BOOTH で公開した日時を UTC で）・`summary`・`release_notes` を書き換え、
   `published` を `true` にする。`booth_url` は公式商品ページのまま変えない。
4. **形式チェック**
   ```
   python tools/check_feed.py validate update.json
   ```
   `結果: 合格` 以外ならコミットしない。表示される版・公開状態・日時が意図どおりかも読む。
5. **GitHub Pages へ反映**
   ```
   git add update.json
   git commit -m "Publish <edition> <version>"
   git push origin main
   ```
   GitHub の Actions タブに表示される `pages build and deployment` が完了するまで待つ（通常 1〜2 分）。
6. **公開 URL の取得結果を確認**
   ```
   python tools/check_feed.py fetch --expect update.json
   ```
   - `HTTP status: 200`、リダイレクトなし、`Content-Type: application/json; charset=utf-8`、`Set-Cookie` なし
   - `取得内容は update.json とバイト単位で一致しています`
   - `結果: 合格`

   GitHub Pages 側にも最大 10 分程度のキャッシュがあるため（応答の `Cache-Control: max-age=600`）、
   一致しない場合は数分おいて再実行する。ブラウザで表示できただけでは合格にしない。
7. **アプリで確認**
   更新前の版（例: 1 つ前の版）を起動し、設定のバージョン番号横の「更新を確認」で新しい版と公式商品ページへの案内が出ること、
   更新後の版では「最新版です」になることを、販売版・体験版それぞれで確認する。

### 初回の扱いについて（重要）

アプリは、**公開済み（`published: true`）の有効な entry を初めて読めたとき**、その版を「既に案内済み」として記録し、
その時点では自動通知を出しません（同じ通知を繰り返さないための仕様）。そのため:

- 利用者が使っている版と **同じ版の entry を公開しておく** と、その時点で記録が作られ、次に新しい版を公開したときに 1 回だけ自動通知されます。
  BOOTH で新しい版を公開したら、上の手順でその版の entry を速やかに公開してください。
- `editions` が空、または `published: false` だけの間は記録が作られません。その状態からいきなり新しい版を公開すると、
  多くの利用者にとってはそれが「初回」になり、その版の自動通知は省略されます（設定の「更新を確認」では表示されます）。

### 販売版だけを先に公開する場合

`editions` の中の `commercial` だけを追加・変更し、`trial` には触れません（無ければ書かない、あれば前の版のまま）。
体験版は自分の entry しか見ないため、販売版の entry を書き換えても体験版の利用者には通知されません。
体験版を公開するときに、同じ手順で `trial` を追加・変更します。体験版だけを先に公開する場合も同様です。

## 公開を取り消す場合

対象 edition の entry を消さずに `published` を `false` にし、手順 4〜6 で反映します（他の項目は変えなくてよい）。
もう一方の edition には触れません。

- 取り消しはすぐには全員に届きません。アプリは取得に成功した更新情報を **最大 24 時間** 手元に保存して自動確認に使うため、
  GitHub Pages 側のキャッシュ（最大 10 分程度）と合わせて、反映まで最大 24 時間ほどかかることがあります。
  設定の「更新を確認」（手動確認）は毎回取得し直すため、そちらには早く反映されます。
- 既に通知を見た利用者の記録は取り消されません。取り消し後に同じ版番号を再公開しても、その利用者には再通知されません。
  修正版を出す場合は版番号を上げてください。
- 版番号を前の版へ戻すことでの取り消しは行わないでください（アプリは一度記録した版より低い版を通知しないため、意味がありません）。

## してはいけないこと

- BOOTH で配布を確認する前に `published: true` にする
- 予定・試験用の版番号や日時を載せる
- 公式商品ページ以外の URL（他の商品、短縮 URL、クエリ付き URL など）を `booth_url` に書く
- `personal` を追加する
- 配布物・ソースコード・利用者データ・トークン類をこのリポジトリに置く
- GitHub Pages の公開元（`main` ブランチの `/`）や URL を変える（アプリは上記の URL だけを読み、リダイレクト先には移動しません）
