/*
 * Hide AV1 from the page's media capability queries on YouTube.
 *
 * Why: YouTube picks a codec by asking the browser what it can play. This
 * device's video engine decodes VP9 (and H.264/HEVC/VP8/MPEG-2) in hardware
 * through VA-API, but the H616/H700 has no AV1 decoder at all, so advertising
 * AV1 gets the page to negotiate AV1 and decode it on the four A53s
 * (200-300 % of one core at 480p). With AV1 hidden, YouTube serves VP9 and the
 * VPU does the work: verified on the device 2026-10-29, the player reports
 * vp09.00.51.08 and libva logs "decoding vp9 via /dev/video0 [cedrus]".
 *
 * Scope: only the three capability APIs YouTube consults, only on youtube.com,
 * and only for AV1 - everything else is passed through untouched. Delete this
 * extension (or its --load-extension flag in /etc/chromium.d/50-rg35xxh) to get
 * stock behaviour back.
 */
(() => {
	const isAV1 = (t) => typeof t === "string" && /av01|av1/i.test(t);

	if (window.MediaSource && MediaSource.isTypeSupported) {
		const orig = MediaSource.isTypeSupported.bind(MediaSource);
		MediaSource.isTypeSupported = (t) => (isAV1(t) ? false : orig(t));
	}

	const cpt = HTMLMediaElement.prototype.canPlayType;
	HTMLMediaElement.prototype.canPlayType = function (t) {
		return isAV1(t) ? "" : cpt.call(this, t);
	};

	if (navigator.mediaCapabilities && navigator.mediaCapabilities.decodingInfo) {
		const orig = navigator.mediaCapabilities.decodingInfo.bind(
			navigator.mediaCapabilities);
		navigator.mediaCapabilities.decodingInfo = (c) =>
			isAV1(JSON.stringify(c))
				? Promise.resolve({
						supported: false,
						smooth: false,
						powerEfficient: false,
				  })
				: orig(c);
	}
})();
