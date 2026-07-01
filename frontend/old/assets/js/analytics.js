// Google Analytics 4 loader. Reads the measurement ID from
// window.SAILFRAMES_GA_ID (set in config.js). No-ops when the ID is
// empty or still the placeholder, so dev/preview deploys don't pollute
// production stats. Load this script AFTER config.js on every page.
(function () {
    var GA_ID = window.SAILFRAMES_GA_ID;
    if (!GA_ID || GA_ID === 'G-XXXXXXXXXX') return;

    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(GA_ID);
    document.head.appendChild(s);

    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    window.gtag = gtag;
    gtag('js', new Date());
    gtag('config', GA_ID, {
        // anonymize_ip is implicit on GA4; explicit for clarity:
        anonymize_ip: true,
    });
})();
