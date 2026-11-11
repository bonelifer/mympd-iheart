(() => {
    function stationLine(anchor, tag) {
        const line = document.createElement(tag);
        line.hidden = true;
        anchor.after(line);
        return line;
    }

    const stationLines = [
        stationLine(document.getElementById("PlaybackTitle"), "p"),
        stationLine(document.getElementById("footerTitle"), "div")
    ];
    const covers = ["PlaybackCover", "footerCover"].map(id => {
        const logo = document.createElement("img");
        logo.alt = "";
        logo.hidden = true;
        logo.classList.add("position-absolute", "top-0", "start-0", "w-100",
            "h-100", "object-fit-contain", "pe-none", "bg-body");
        logo.addEventListener("error", () => { logo.hidden = true; });
        document.getElementById(id).append(logo);
        return logo;
    });
    const assetBase = new URL(".", document.currentScript.src);
    const picker = document.createElement("button");
    picker.type = "button";
    picker.className = "btn px-2 mi rounded-2 d-none";
    picker.textContent = "tune";
    picker.title = "Open iHeartRadio station picker";
    picker.setAttribute("aria-label", picker.title);
    picker.addEventListener("click", () => {
        sendAPI("MYMPD_API_SCRIPT_EXECUTE", {
            script: "iHeartRadio Favorites",
            event: "user",
            arguments: {mode: "play"}
        }, null, false);
    });
    document.getElementById("footerNextBtn")?.after(picker);

    function titleCase(value) {
        return value.split(/(\s+[-–—/]\s+)/u).map(part => {
            if (part === part.toLowerCase() || part !== part.toUpperCase()) {
                return part;
            }
            return part.toLowerCase().replace(/(^|[^\p{L}\p{N}'’])(\p{L})/gu,
                (_, prefix, first) => prefix + first.toUpperCase());
        }).join("");
    }

    function trackTitle(value) {
        const match = value.match(/^(.+?\s+-\s+)text="([^"]+)"(?:\s+\w+="[^"]*")+\s*$/u);
        return match ? match[1] + match[2] : value;
    }

    const stationLabels = ["footerAlbum", "currentName"].map(
        id => document.getElementById(id)
    );
    const hiddenLabels = new Map();

    function stationKey(value) {
        return value.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
    }

    function update() {
        const fragment = (currentSongObj?.uri ?? "").split("#")[1] ?? "";
        const metadata = new URLSearchParams(fragment);
        const id = metadata.get("mympd-iheart") ?? "";
        const isIHeart = /^\d+$/.test(id);
        picker.classList.toggle("d-none", !isIHeart);
        const stationName = metadata.get("name") ?? "";
        const artwork = metadata.get("art") ?? "";
        for (const line of stationLines) {
            line.hidden = !isIHeart || stationName === "";
            if (!line.hidden) {
                line.textContent = stationName;
            }
        }
        const hasArtwork = isIHeart && (artwork === id + ".jpg" || artwork === id + ".png");
        for (const logo of covers) {
            if (!hasArtwork) {
                logo.hidden = true;
                logo.removeAttribute("src");
            } else {
                const src = new URL("iheart-stations/" + artwork, assetBase).href;
                if (logo.src !== src) {
                    logo.src = src;
                    logo.hidden = false;
                }
            }
        }
        const stationLabel = stationKey(stationName);
        for (const element of stationLabels) {
            if (element) {
                const duplicate = isIHeart && stationLabel !== ""
                    && stationKey(element.querySelector("p")?.textContent ?? element.textContent)
                        === stationLabel;
                if (duplicate && !hiddenLabels.has(element)) {
                    hiddenLabels.set(element, element.style.display);
                    element.style.display = "none";
                } else if (!duplicate && hiddenLabels.has(element)) {
                    element.style.display = hiddenLabels.get(element);
                    hiddenLabels.delete(element);
                }
            }
        }
        if (!isIHeart) {
            return;
        }
        for (const id of ["PlaybackTitle", "footerTitle", "footerArtist"]) {
            const element = document.getElementById(id);
            if (element?.textContent) {
                const formatted = titleCase(trackTitle(element.textContent));
                if (formatted !== element.textContent) {
                    element.textContent = formatted;
                }
            }
        }
    }

    const observer = new MutationObserver(update);
    const titleElements = ["PlaybackTitle", "footerTitle", "footerArtist"].map(
        id => document.getElementById(id)
    );
    for (const element of [...titleElements, ...stationLabels]) {
        if (element) {
            observer.observe(element, {childList: true, characterData: true, subtree: true});
        }
    }
    update();
})();
