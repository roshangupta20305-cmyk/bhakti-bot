BHAKTI AUTOBOT (sirf Android phone se, sab free)
Telegram par /make likho -> GitHub ka free server: topic -> script -> keyframes + awaaz (Gemini) -> Kaggle T4 GPU par video
+ lip-sync -> Gemini quality check, kharab clip dobara -> final edit -> video aapke Telegram par.
"Post karo" dabao -> YouTube Shorts + Instagram Reels + Facebook Reels. Roz 5 baje shaam khud bhi ek video banata hai.

SETUP (sab Chrome mein, ek baar)
1. Telegram: @BotFather -> /newbot -> TOKEN copy. @userinfobot -> apna Id copy.
2. aistudio.google.com -> Get API key.
3. kaggle.com: phone verify karo -> Settings -> API -> Create New Token (kaggle.json mein username aur key).
4. github.com par account -> New repository -> naam "bhakti-bot" -> PUBLIC (tabhi free minutes unlimited) -> Create.
   Is zip ko phone ke Files app mein Extract karo. Repo mein "Add file > Upload files" -> saari files ek saath chuno -> Commit.
   music.mp3 (copyright-free flute + tanpura) aur bell.mp3 bhi isi tarah upload karo.
5. "Add file > Create new file" -> naam likho:  .github/workflows/make.yml   -> WORKFLOW_make.yml.txt ka poora text paste -> Commit.
   Phir se:  .github/workflows/listen.yml   -> WORKFLOW_listen.yml.txt ka text paste -> Commit.
6. Repo Settings -> Secrets and variables -> Actions -> New repository secret, ye sab daalo:
   GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID, KAGGLE_USERNAME, KAGGLE_KEY
   (posting ke liye, step 7-8 ke baad): META_PAGE_TOKEN, FB_PAGE_ID, IG_USER_ID, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
   Settings -> Actions -> General -> Workflow permissions -> "Read and write" -> Save.
7. YouTube: console.cloud.google.com -> project -> "YouTube Data API v3" Enable -> OAuth consent screen (External, apna email test user)
   -> Credentials -> OAuth client ID -> "Web application", redirect URI: https://developers.google.com/oauthplayground
   -> Client ID/Secret copy. developers.google.com/oauthplayground -> settings (gear) -> "Use your own OAuth credentials" ->
   scope: https://www.googleapis.com/auth/youtube.upload -> Authorize -> Exchange -> Refresh token copy.
   Consent screen ko "In production" karo, warna refresh token 7 din mein expire.
   Naye project se upload PRIVATE lock rehte hain jab tak YouTube API audit (free form) pass na ho; tab tak variable YT_PRIVACY=private.
8. Instagram ko Professional account banao, Facebook Page se jodo. developers.facebook.com -> App -> Graph API Explorer ->
   permissions: instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, pages_manage_posts, publish_video
   -> Page token -> Access Token Debugger mein "Extend" (long-lived). FB_PAGE_ID aur IG_USER_ID wahin se.
9. Telegram par apne bot ko /start bhejo. 15-20 min mein jawab aayega. Phir /ideas ya /make Hanuman ji ka Sanjeevani laana

JAANKARI
- Telegram commands ka jawab 15-20 min mein aata hai (GitHub har 15 min check karta hai).
- Ek video ~1.5-2 ghante. Kaggle ka weekly GPU quota jitna, utne video.
- Roz wala auto video band karna ho: make.yml se "schedule" wali 2 line hata do.
- Ant ki line (Jai Shri Ram) brain.py mein ENDING hai.
