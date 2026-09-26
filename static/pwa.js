// Registers the service worker so the app can be installed on a phone
// and opens with its own icon, like a normal app.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function (err) {
      console.log("Service worker registration failed:", err);
    });
  });
}
