(function () {
  const shared = {
    testing: {
      introTitle: "Generated variants for this failure pattern",
      introBody:
        "These responses are generated from the exact breakdown in Run #47 (defer - cancel - ticket system 422). Pick one and deploy with staged safety checks.",
      validationBody:
        "Model family benchmark: 3,420 prior production calls, 91.6% success rate on defer/escalation recovery flows, 97.9% ticket system write success with retry enabled.",
      rolloutBody:
        "Deploy selected variant to 10% traffic for 30 minutes, then 50% for 2 hours if cancel sync stays above 97%, then 100% rollout.",
    },
    callBreakdown: {
      recommendation:
        "Add a customer-escalation handoff path: confirm escalation verbally, map to correct Zendesk field/status, and add retry + alert on sync failure. Use generated variants to test this flow.",
    },
  };

  function setText(selector, text) {
    const el = document.querySelector(selector);
    if (el && typeof text === "string") el.textContent = text;
  }

  function applyTestingCopy() {
    setText("main.main-content h1", shared.testing.introTitle);
    setText("main.main-content .mb-6 > p.text-text-light", shared.testing.introBody);
    setText("main.main-content .bg-green-50 p.text-sm.text-text-medium", shared.testing.validationBody);
    setText("main.main-content .bg-blue-50 h3 + p.text-sm.text-text-medium", shared.testing.rolloutBody);
  }

  function applyCallBreakdownCopy() {
    const rootCauseColumns = document.querySelectorAll("main.main-content .bg-red-50\\/80 .grid > div");
    if (rootCauseColumns.length >= 3) {
      const rec = rootCauseColumns[2].querySelector("p.text-text-medium");
      if (rec) rec.textContent = shared.callBreakdown.recommendation;
    }
  }

  window.applyPokantSharedCopy = function applyPokantSharedCopy() {
    applyTestingCopy();
    applyCallBreakdownCopy();
  };
})();
