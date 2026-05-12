window.SAILFRAMES_API_URL = 'https://rnngzx7flk.execute-api.us-east-1.amazonaws.com';

// Google Analytics 4 measurement ID. Set to your G-XXXXXXXXXX to enable
// page-view tracking site-wide. Leave empty (or as the placeholder
// below) to disable tracking — analytics.js no-ops in that case.
window.SAILFRAMES_GA_ID = 'G-DBRW152J6H';

// Coach app — fill these in once the api_coach Lambda is deployed and a
// Google OAuth Client ID is created in Google Cloud Console.
//   SAILFRAMES_COACH_API:           the Function URL for the api_coach Lambda
//                                   (e.g., https://xxxxxx.lambda-url.us-east-1.on.aws)
//   SAILFRAMES_GOOGLE_CLIENT_ID:    OAuth 2.0 Client ID (Web application)
//                                   from console.cloud.google.com → APIs & Services
//                                   → Credentials. Authorized JavaScript origins
//                                   must include https://sailframes.com.
window.SAILFRAMES_COACH_API = 'https://vt6gjqnzbu4x64sh7yxt4bak3m0gegyg.lambda-url.us-east-1.on.aws';
window.SAILFRAMES_GOOGLE_CLIENT_ID = '1021303267690-l1lcsudicgj8ucv473j6p4950gmn3glh.apps.googleusercontent.com';
