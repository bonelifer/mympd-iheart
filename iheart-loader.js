(() => {
    const script = document.createElement("script");
    const url = new URL("browse/pics/iheart-display.js?v=10", document.currentScript.src).href;
    const policy = window.trustedTypes?.createPolicy("iheart-player", {
        createScriptURL(candidate) {
            if (candidate !== url) {
                throw new TypeError("Unexpected iHeartRadio script URL");
            }
            return url;
        }
    });
    script.src = policy ? policy.createScriptURL(url) : url;
    document.head.append(script);
})();
