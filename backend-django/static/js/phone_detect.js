/* Phone country detector + formatter for the LMS.
 *
 * Wraps libphonenumber-js (loaded as the global `libphonenumber` from the
 * bundle in base/page templates). Exposes a single clean function:
 *
 *   detectAndFormatPhoneNumber(input) -> {
 *     countryCode,      // e.g. "+91"
 *     formattedNumber,  // E.164, e.g. "+919876543210"
 *     country,          // ISO region, e.g. "IN"
 *     isValid,          // boolean
 *     error?            // present when isValid is false
 *   }
 *
 * Reality check baked into the heuristic: a bare national number carries no
 * country fingerprint. We resolve it by trying a priority-ordered candidate
 * list (most populous / common-use first) and returning the FIRST country the
 * number is actually valid for. Numbers that already carry a "+" (or "00")
 * are parsed directly and their real country is used — no guessing.
 */
(function (global) {
  "use strict";

  // Candidate countries for bare numbers, ordered by likelihood (population /
  // common CRM use). India first since this is an Indian LMS.
  var CANDIDATES = [
    "IN", "US", "GB", "CA", "AU", "DE", "FR", "AE", "SG", "PK",
    "BD", "NP", "LK", "ZA", "NG", "BR", "MX", "ID", "PH", "MY",
    "IT", "ES", "NL", "SE", "CH", "IE", "NZ", "SA", "QA", "KW",
  ];

  var ISO_TO_NAME = {
    IN: "India", US: "United States", GB: "United Kingdom", CA: "Canada",
    AU: "Australia", DE: "Germany", FR: "France", AE: "UAE", SG: "Singapore",
    PK: "Pakistan", BD: "Bangladesh", NP: "Nepal", LK: "Sri Lanka",
    ZA: "South Africa", NG: "Nigeria", BR: "Brazil", MX: "Mexico",
    ID: "Indonesia", PH: "Philippines", MY: "Malaysia", IT: "Italy",
    ES: "Spain", NL: "Netherlands", SE: "Sweden", CH: "Switzerland",
    IE: "Ireland", NZ: "New Zealand", SA: "Saudi Arabia", QA: "Qatar",
    KW: "Kuwait",
  };

  function lpn() {
    var lib = global.libphonenumber;
    if (!lib) throw new Error("libphonenumber-js bundle not loaded");
    return lib;
  }

  // ISO region -> emoji flag (🇮🇳 etc.) by offsetting into regional indicators.
  function flagEmoji(iso) {
    if (!iso || iso.length !== 2) return "🌐";
    return String.fromCodePoint(...[...iso.toUpperCase()].map(c => 0x1f1e6 + c.charCodeAt(0) - 65));
  }

  function countryName(iso) {
    return ISO_TO_NAME[iso] || iso;
  }

  function clean(input) {
    // Strip spaces, dashes, parens, dots; keep leading + and digits.
    var s = String(input || "").trim().replace(/[\s().\-]/g, "");
    if (s.indexOf("00") === 0) s = "+" + s.slice(2); // 00 = intl prefix
    return s;
  }

  function fail(error) {
    return { countryCode: "", formattedNumber: "", country: "", isValid: false, error: error };
  }

  function detectAndFormatPhoneNumber(input) {
    var lib;
    try { lib = lpn(); } catch (e) { return fail(e.message); }

    var raw = clean(input);
    if (!raw) return fail("Empty number");

    var digits = raw.replace(/\D/g, "");
    if (digits.length < 7) return fail("Too short to be a valid number");

    // Case 1: number carries its own country code (leading +). Trust it.
    if (raw[0] === "+") {
      try {
        var parsed = lib.parsePhoneNumber(raw);
        if (parsed && parsed.isValid()) {
          return {
            countryCode: "+" + parsed.countryCallingCode,
            formattedNumber: parsed.number, // E.164
            country: parsed.country || "",
            isValid: true,
          };
        }
      } catch (e) { /* fall through */ }
      return fail("Invalid international number");
    }

    // Case 2: bare national number. Try candidates in priority order; return
    // the first country it's genuinely valid for.
    for (var i = 0; i < CANDIDATES.length; i++) {
      var region = CANDIDATES[i];
      try {
        if (lib.isValidPhoneNumber(raw, region)) {
          var p = lib.parsePhoneNumber(raw, region);
          return {
            countryCode: "+" + p.countryCallingCode,
            formattedNumber: p.number,
            country: p.country || region,
            isValid: true,
          };
        }
      } catch (e) { /* try next */ }
    }

    return fail("Could not match this number to a known country");
  }

  global.PhoneDetect = {
    detectAndFormatPhoneNumber: detectAndFormatPhoneNumber,
    flagEmoji: flagEmoji,
    countryName: countryName,
    CANDIDATES: CANDIDATES,
  };
})(window);
