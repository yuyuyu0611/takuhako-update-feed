#!/usr/bin/env python3
"""卓ハコ更新情報 ``update.json`` の公開前チェックと公開URLの取得チェック。

標準ライブラリだけで動く(Python 3.8以上)。卓ハコ本体のコードは使わない。
ここでの検査は公開形式 ``takuhako-update-feed/1`` の取り決めをなぞったもので、
アプリ側の判定はこれと同等以上に厳しい。迷ったら「通知が出ない」側に倒すこと。

使い方:
    python tools/check_feed.py validate update.json
    python tools/check_feed.py fetch https://yuyuyu0611.github.io/takuhako-update-feed/update.json --expect update.json

終了コード: 0=合格 / 1=不合格 / 2=使い方の誤り
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SCHEMA = "takuhako-update-feed/1"
APP_ID = "takuhako"
CHANNEL = "stable"
EDITIONS = ("commercial", "trial")  # personal(個人版)は登録しない
OFFICIAL_BOOTH_URL = "https://yuaso-syuttyou.booth.pm/items/8709668"
FEED_URL = "https://yuyuyu0611.github.io/takuhako-update-feed/update.json"

MAX_BYTES = 64 * 1024
MAX_DEPTH = 8
MAX_SUMMARY = 500
MAX_NOTES = 2000
TOP_KEYS = {"schema", "app_id", "channel", "editions"}
ENTRY_KEYS = {"version", "published", "published_at", "booth_url", "summary", "release_notes"}
VERSION_RE = re.compile(r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})")
TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
BAD_TEXT_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f‪-‮⁦-⁩]")


class CheckError(Exception):
    pass


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise CheckError(f"同じキーが2回あります: {key!r}")
        seen[key] = value
    return seen


def _no_numbers(text):
    raise CheckError(f"数値は使えません(文字列で書く): {text!r}")


def _depth(value) -> int:
    if isinstance(value, dict):
        return 1 + max([0] + [_depth(v) for v in value.values()])
    if isinstance(value, list):
        return 1 + max([0] + [_depth(v) for v in value])
    return 0


def validate_bytes(raw: bytes, *, now: datetime) -> list:
    """不合格なら CheckError。合格なら注意事項(list[str])を返す。"""
    notes = []
    if not raw:
        raise CheckError("空のファイルです")
    if len(raw) > MAX_BYTES:
        raise CheckError(f"64KiBを超えています({len(raw)} bytes)")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise CheckError("BOM付きUTF-8です。BOMなしで保存してください")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CheckError(f"UTF-8として読めません: {exc}") from None
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates,
                          parse_int=_no_numbers, parse_float=_no_numbers, parse_constant=_no_numbers)
    except json.JSONDecodeError as exc:
        raise CheckError(f"JSONの書式が正しくありません: {exc}") from None
    if _depth(data) > MAX_DEPTH:
        raise CheckError("入れ子が深すぎます")
    if not isinstance(data, dict) or set(data) != TOP_KEYS:
        raise CheckError(f"最上位のキーは {sorted(TOP_KEYS)} ちょうどにしてください")
    for key, expected in (("schema", SCHEMA), ("app_id", APP_ID), ("channel", CHANNEL)):
        if data[key] != expected:
            raise CheckError(f"{key} は {expected!r} にしてください(現在 {data[key]!r})")
    editions = data["editions"]
    if not isinstance(editions, dict):
        raise CheckError("editions はオブジェクト({ })にしてください")
    for name in editions:
        if name not in EDITIONS:
            raise CheckError(f"editions に {name!r} は書けません(使えるのは {', '.join(EDITIONS)} だけ)")
    if not editions:
        notes.append("editions が空です: どの版にも更新通知は出ません")
    for name in EDITIONS:
        if name not in editions:
            continue
        entry = editions[name]
        where = f"editions.{name}"
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise CheckError(f"{where} のキーは {sorted(ENTRY_KEYS)} ちょうどにしてください")
        if not isinstance(entry["version"], str) or not VERSION_RE.fullmatch(entry["version"]):
            raise CheckError(f"{where}.version は 1.4.3 のような半角の「数字.数字.数字」にしてください"
                             f"(v前置・-rc・先頭0は不可) 現在 {entry['version']!r}")
        if type(entry["published"]) is not bool:
            raise CheckError(f"{where}.published は true か false(引用符なし)にしてください")
        stamp = entry["published_at"]
        if not isinstance(stamp, str) or not TIME_RE.fullmatch(stamp):
            raise CheckError(f"{where}.published_at は 2026-01-31T12:00:00Z の形(UTC・末尾Z)にしてください")
        try:
            published_at = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            raise CheckError(f"{where}.published_at が存在しない日時です: {stamp}") from None
        if entry["booth_url"] != OFFICIAL_BOOTH_URL:
            raise CheckError(f"{where}.booth_url は公式商品ページ {OFFICIAL_BOOTH_URL} と完全一致させてください")
        for field, limit in (("summary", MAX_SUMMARY), ("release_notes", MAX_NOTES)):
            value = entry[field]
            if not isinstance(value, str):
                raise CheckError(f"{where}.{field} は文字列にしてください")
            if len(value) > limit:
                raise CheckError(f"{where}.{field} は{limit}文字以内にしてください(現在{len(value)}文字)")
            if BAD_TEXT_RE.search(value):
                raise CheckError(f"{where}.{field} に制御文字・方向制御文字が含まれています")
        state = "公開(published=true)" if entry["published"] else "非公開(published=false)"
        notes.append(f"{name}: v{entry['version']} {state} 公開日時 {stamp}")
        if entry["published"] and published_at > now:
            notes.append(f"注意 {name}: 公開日時が未来です。その時刻を過ぎるまで通知は出ません")
    return notes


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CheckError(f"リダイレクトされました(HTTP {code} → {newurl})。このURLは使えません")


def _content_type_ok(value: str) -> bool:
    parts = [p.strip().lower() for p in (value or "").split(";")]
    if parts[0] != "application/json":
        return False
    for param in parts[1:]:
        if not param:
            continue
        name, _, raw = param.partition("=")
        if name.strip() != "charset" or raw.strip().strip('"') not in {"utf-8", "utf8"}:
            return False
    return True


def fetch(url: str, *, expect_path: str = None, now: datetime) -> int:
    if not url.startswith("https://") or "?" in url or "#" in url:
        print(f"NG: https:// で始まり ? と # を含まないURLにしてください: {url}")
        return 1
    opener = urllib.request.build_opener(
        _RefuseRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),  # 証明書検証あり
    )
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "takuhako-update-feed-check/1",
    })
    try:
        with opener.open(request, timeout=15) as response:
            status = response.status
            headers = response.headers
            body = response.read(MAX_BYTES + 1)
    except CheckError as exc:
        print(f"NG: {exc}")
        return 1
    except urllib.error.HTTPError as exc:
        print(f"NG: HTTP {exc.code}")
        return 1
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        print(f"NG: 取得できません(通信/TLS): {exc}")
        return 1
    print(f"URL: {url}")
    print(f"HTTP status: {status}")
    for name in ("Content-Type", "Content-Length", "Content-Encoding", "ETag", "Last-Modified",
                 "Cache-Control", "Expires", "Age", "Set-Cookie"):
        print(f"  {name}: {headers.get(name)}")
    failed = False
    if status != 200:
        print("NG: HTTP 200 ではありません")
        failed = True
    if not _content_type_ok(headers.get("Content-Type", "")):
        print("NG: Content-Type が application/json(charset=utf-8可)ではありません")
        failed = True
    if (headers.get("Content-Encoding") or "identity").lower() != "identity":
        print("NG: 圧縮されたまま返されました")
        failed = True
    if headers.get("Set-Cookie"):
        print("NG: Cookie が設定されています")
        failed = True
    try:
        for note in validate_bytes(body, now=now):
            print(f"  {note}")
    except CheckError as exc:
        print(f"NG: 取得したJSONが形式に合いません: {exc}")
        failed = True
    if expect_path:
        with open(expect_path, "rb") as handle:
            local = handle.read()
        if body == local:
            print(f"取得内容は {expect_path} とバイト単位で一致しています")
        else:
            print(f"NG: 取得内容が {expect_path} と一致しません(反映待ちの可能性。数分おいて再実行)")
            failed = True
    print("結果: " + ("不合格" if failed else "合格"))
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="卓ハコ更新情報JSONのチェック")
    sub = parser.add_subparsers(dest="command", required=True)
    p_validate = sub.add_parser("validate", help="ローカルのJSONファイルを検査する")
    p_validate.add_argument("path")
    p_fetch = sub.add_parser("fetch", help="公開URLから取得して検査する")
    p_fetch.add_argument("url", nargs="?", default=FEED_URL)
    p_fetch.add_argument("--expect", help="取得結果と完全一致するはずのローカルファイル")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.command == "validate":
        with open(args.path, "rb") as handle:
            raw = handle.read()
        try:
            notes = validate_bytes(raw, now=now)
        except CheckError as exc:
            print(f"NG: {exc}")
            return 1
        for note in notes:
            print(f"  {note}")
        print("結果: 合格")
        return 0
    return fetch(args.url, expect_path=args.expect, now=now)


if __name__ == "__main__":
    sys.exit(main())
