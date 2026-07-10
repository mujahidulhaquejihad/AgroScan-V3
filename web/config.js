// AgroVet V2 web config.
(function () {
  function apiBase() {
    var loc = window.location;
    // Opened as a local file -> point at the server on this machine
    if (loc.protocol === "file:") return "http://127.0.0.1:8000";
    // http/https: always use SAME ORIGIN as the page.
    // This works for localhost:8000, VS Code port forwarding, and tunnels.
    if (loc.protocol === "http:" || loc.protocol === "https:") return "";
    return "";
  }

  window.AGROVET_CONFIG = {
    API_BASE: apiBase(),
    // Paste your Google OAuth Web Client ID here (Cloud Console → Credentials).
    // Add http://localhost:8000 to Authorized JavaScript origins.
    GOOGLE_CLIENT_ID: "145820214796-5fl72t2u8e2mnfa73n94ejk1kv3v69af.apps.googleusercontent.com",
  };
})();
