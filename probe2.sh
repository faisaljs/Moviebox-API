#!/usr/bin/env bash
set -u

UP="https://h5-api.aoneroom.com/wefeed-h5api-bff"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
REF="https://moviebox.ph/"
ORG="https://moviebox.ph"

SID="1814538579394059168"
SLUG="ramayana-hindi-cam-qjbmxfzB2a2"

echo "════════ 0. Restart the app before running this. Then: ════════"
curl -s http://127.0.0.1:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('tokens_cached AFTER RESTART:', d['tokens_cached'])"

echo
echo "════════ 1. Hit /home, then check token cache again ════════"
curl -s http://127.0.0.1:8000/home > /dev/null
curl -s http://127.0.0.1:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('tokens_cached AFTER /home:', d['tokens_cached'])"

echo
echo "════════ 2. Harvest a guest token from /home (curl) ════════"
TOKEN=$(curl -si "$UP/home?host=moviebox.ph" -H "User-Agent: $UA" \
  | awk 'BEGIN{IGNORECASE=1} /^x-user:/{sub(/^x-user: */,""); print}' \
  | tr -d '\r' \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read() or '{}').get('token',''))" 2>/dev/null)
echo "harvested token: ${TOKEN:0:40}... (len=${#TOKEN})"

echo
echo "════════ 3. /subject/search WITH Authorization: Bearer ════════"
curl -si -X POST "$UP/subject/search?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" -H "Origin: $ORG" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"keyword":"matrix","page":1,"perPage":20}' | head -15

echo
echo "════════ 4. /subject/search WITH Cookie: token= ════════"
curl -si -X POST "$UP/subject/search?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" -H "Origin: $ORG" \
  -H "Content-Type: application/json" \
  -H "Cookie: token=$TOKEN" \
  -d '{"keyword":"matrix","page":1,"perPage":20}' | head -15

echo
echo "════════ 5. /subject/search WITH BOTH ════════"
curl -si -X POST "$UP/subject/search?host=moviebox.ph" \
  -H "User-Agent: $UA" -H "Referer: $REF" -H "Origin: $ORG" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Cookie: token=$TOKEN" \
  -d '{"keyword":"matrix","page":1,"perPage":20}' | head -15

echo
echo "════════ 6. /subject/play — try EVERY plausible location ════════"

try_play() {
  local label="$1" url="$2" referer="$3"
  echo "──── $label ────"
  curl -si "$url" \
    -H "User-Agent: $UA" \
    -H "Referer: $referer" \
    -H "Authorization: Bearer $TOKEN" | head -12
  echo
}

# 6a. API base, moviebox referer
try_play "h5-api /subject/play + moviebox referer" \
  "$UP/subject/play?subjectId=$SID&se=0&ep=0&detailPath=$SLUG&host=moviebox.ph" \
  "$REF"

# 6b. API base, mzfi.me referer
try_play "h5-api /subject/play + mzfi.me referer" \
  "$UP/subject/play?subjectId=$SID&se=0&ep=0&detailPath=$SLUG&host=moviebox.ph" \
  "https://mzfi.me/spa/videoPlayPage/movies/$SLUG?id=$SID&type=/movie/detail&detailSe=0&detailEp=0&lang=en"

# 6c. current app path on mzfi.me (expected to fail — should be HTML)
try_play "mzfi.me /wefeed-h5api-bff/subject/play (current)" \
  "https://mzfi.me/wefeed-h5api-bff/subject/play?subjectId=$SID&se=0&ep=0&detailPath=$SLUG" \
  "https://mzfi.me/"

# 6d. old domain netfilm.world
try_play "netfilm.world /wefeed-h5api-bff/subject/play" \
  "https://netfilm.world/wefeed-h5api-bff/subject/play?subjectId=$SID&se=0&ep=0&detailPath=$SLUG" \
  "https://netfilm.world/spa/videoPlayPage/movies/$SLUG?id=$SID&type=/movie/detail&detailSe=0&detailEp=0&lang=en"

echo
echo "════════ 7. What does mzfi.me actually return for /? ════════"
curl -si "https://mzfi.me/" -H "User-Agent: $UA" | head -20
echo
echo "──── first 500 bytes of mzfi.me / body ────"
curl -s "https://mzfi.me/" -H "User-Agent: $UA" | head -c 500
echo

echo
echo "════════ 8. Does the mzfi.me 3885-byte response contain hints? ════════"
curl -s "https://mzfi.me/wefeed-h5api-bff/subject/play?subjectId=$SID&se=0&ep=0&detailPath=$SLUG" \
  -H "User-Agent: $UA" | head -c 800
echo