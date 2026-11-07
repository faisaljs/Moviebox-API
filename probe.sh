#!/usr/bin/env bash
set -u

UP="https://h5-api.aoneroom.com/wefeed-h5api-bff"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
REF="https://moviebox.ph/"
ORG="https://moviebox.ph"

echo "════════ 1. /home response headers (where does the token live?) ════════"
curl -si "$UP/home?host=moviebox.ph" -H "User-Agent: $UA" -H "Referer: $REF" | head -30

echo
echo "════════ 2. /subject/search current payload — full response ════════"
curl -si -X POST "$UP/subject/search?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" -H "Origin: $ORG" \
  -H "Content-Type: application/json" \
  -d '{"keyword":"matrix","page":1,"perPage":20}' | head -30

echo
echo "════════ 3. /subject/search smaller perPage=10 ════════"
curl -si -X POST "$UP/subject/search?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" -H "Origin: $ORG" \
  -H "Content-Type: application/json" \
  -d '{"keyword":"matrix","page":1,"perPage":10}' | head -15

echo
echo "════════ 4. /subject/search no page field ════════"
curl -si -X POST "$UP/subject/search?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" -H "Origin: $ORG" \
  -H "Content-Type: application/json" \
  -d '{"keyword":"matrix","perPage":10}' | head -15

echo
echo "════════ 5. /subject/search as GET ════════"
curl -si "$UP/subject/search?host=moviebox.ph&keyword=matrix&page=1&perPage=20" \
  -H "User-Agent: $UA" -H "Referer: $REF" | head -15

echo
echo "════════ 6. /subject/search-suggest (control — this works in the app) ════════"
curl -si -X POST "$UP/subject/search-suggest?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" \
  -H "Content-Type: application/json" \
  -d '{"keyword":"matrix","perPage":10}' | head -20

echo
echo "════════ 7. /media-player/get-domain ════════"
curl -si "$UP/media-player/get-domain?host=moviebox.ph" -H "User-Agent: $UA" | head -25

echo
echo "════════ 8. player /subject/play — first resolve domain, then try se/ep variants ════════"
DOM=$(curl -s "$UP/media-player/get-domain?host=moviebox.ph" -H "User-Agent: $UA" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('data') or 'https://netfilm.world')" 2>/dev/null)
echo "resolved player domain: $DOM"

SID="1814538579394059168"
SLUG="ramayana-hindi-cam-qjbmxfzB2a2"

for pair in "0:0" "0:1" "1:1"; do
  SE="${pair%:*}"; EP="${pair#*:}"
  echo
  echo "──── 8.$pair se=$SE ep=$EP ────"
  curl -si "$DOM/wefeed-h5api-bff/subject/play?subjectId=$SID&se=$SE&ep=$EP&detailPath=$SLUG" \
    -H "User-Agent: $UA" \
    -H "Referer: $DOM/spa/videoPlayPage/movies/$SLUG?id=$SID&type=/movie/detail&detailSe=$SE&detailEp=$EP&lang=en" \
    | head -20
done