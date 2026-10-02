// Shared New/Edit Lead modal. Submits to DRF /api (POST create, PUT update).
const $ = (id) => document.getElementById(id);
const modal = $("leadModal");

function lmAddPhone(val = "") {
  const container = $("lm_extra_phones");
  if (!container) return; // Skip if container doesn't exist
  const wrap = document.createElement("div");
  wrap.className = "mt-2 flex gap-2";
  wrap.innerHTML = `<input type="tel" class="lm-inp lm-extra" placeholder="Additional mobile" value="${val}" />
    <button type="button" class="shrink-0 rounded-lg p-2 text-red-400 hover:bg-red-50"><i data-lucide="x" class="h-4 w-4"></i></button>`;
  wrap.querySelector("button").onclick = () => wrap.remove();
  container.appendChild(wrap);
  lucide.createIcons();
}

function syncWa() {
  const same = $("lm_wa_same").checked;
  $("lm_whatsapp").style.display = same ? "none" : "block";
  if (same) $("lm_whatsapp").value = $("lm_phone").value;
}
document.addEventListener("change", (e) => { if (e.target.id === "lm_wa_same") syncWa(); });
document.addEventListener("input", (e) => { if (e.target.id === "lm_phone" && $("lm_wa_same").checked) $("lm_whatsapp").value = e.target.value; });

function lmToggleReferralField() {
  const isReferral = [...document.querySelectorAll(".lm-source-check:checked")].some(cb => cb.value === "referral");
  const wrap = $("lm_referral_wrap");
  if (wrap) wrap.style.display = isReferral ? "" : "none";
}

function lmRenderSourceLabel() {
  const checked = [...document.querySelectorAll(".lm-source-check:checked")];
  const label = document.getElementById("lm_source_label");
  if (!label) return;
  if (!checked.length) { label.textContent = "Select source…"; return; }
  if (checked.length === 1) {
    label.textContent = checked[0].value.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  } else {
    label.textContent = `${checked.length} sources`;
  }
}

function lmRenderProductLabel() {
  const checked = [...document.querySelectorAll(".lm-product-check:checked")];
  const label = document.getElementById("lm_product_label");
  if (!label) return;
  if (!checked.length) { label.textContent = "Select product…"; return; }
  if (checked.length === 1) {
    const opt = document.querySelector(`label[for="lm_product_${checked[0].value}"]`);
    label.textContent = opt ? opt.textContent : checked[0].value;
  } else {
    label.textContent = `${checked.length} products`;
  }
}

function lmShowStep(n) {
  $("lm_step1").classList.toggle("hidden", n !== 1);
  $("lm_step2").classList.toggle("hidden", n !== 2);
  $("lm_step_indicator").textContent = `Step ${n} of 2`;
  if (window.lucide) lucide.createIcons();
}

async function lmNext() {
  $("lm_error1").classList.add("hidden");
  const fail = (msg) => { $("lm_error1").textContent = msg; $("lm_error1").classList.remove("hidden"); };

  const phone = $("lm_phone").value.trim();
  if (!phone) return $("lm_phone").reportValidity();
  const dialCode = ($("lm_country_code") && $("lm_country_code").value) || "+91";
  const expectedLen = (typeof lmGetPhoneLen === "function" ? lmGetPhoneLen(dialCode) : null) || 10;
  if (!new RegExp(`^\\d{${expectedLen}}$`).test(phone)) return fail(`M. Number must be exactly ${expectedLen} digits.`);

  if (!$("lm_full_name").value.trim()) return $("lm_full_name").reportValidity();

  const wa = $("lm_wa_same").checked ? $("lm_phone").value : $("lm_whatsapp").value;
  if (!wa.trim()) return fail("WhatsApp number is required.");
  if (![...document.querySelectorAll(".lm-product-check:checked")].length) return fail("Please select at least one product.");
  if (![...document.querySelectorAll(".lm-source-check:checked")].length) return fail("Please select at least one source.");

  const isReferral = [...document.querySelectorAll(".lm-source-check:checked")].some(cb => cb.value === "referral");
  if (isReferral && !$("lm_referral_name").value.trim()) return fail("Referral Name is required when Source is Referral.");

  // Check for duplicates
  const duplicate = await checkDuplicatePhone();
  if (duplicate && !$("lm_id").value) {
    openMergeModal(duplicate);
    return;
  }

  lmShowStep(2);
}

function lmBack() { lmShowStep(1); }

// Make sure <select id> has an <option value=id>; append one (with the given label)
// if it's missing, so an edited lead's real value can be shown and kept.
function lmEnsureOption(id, value, label) {
  const sel = $(id);
  if (!sel || value == null || value === "" || !label) return;
  if ([...sel.options].some((o) => String(o.value) === String(value))) return;
  const opt = document.createElement("option");
  opt.value = value;
  opt.textContent = label;
  sel.appendChild(opt);
}

function openLeadModal(lead = null) {
  $("leadForm").reset();
  const extraPhonesEl = $("lm_extra_phones");
  if (extraPhonesEl) extraPhonesEl.innerHTML = "";
  $("lm_error").classList.add("hidden");
  $("lm_error1").classList.add("hidden");
  lmShowStep(1);
  document.querySelectorAll(".lm-source-check").forEach(cb => { cb.checked = false; });
  lmRenderSourceLabel();
  if ($("lm_referral_name")) $("lm_referral_name").value = "";
  lmToggleReferralField();
  document.querySelectorAll(".lm-product-check").forEach(cb => { cb.checked = false; });
  lmRenderProductLabel();
  if ($("lm_country_code")) $("lm_country_code").value = "+91";
  if ($("lm_country_label")) $("lm_country_label").textContent = "IND +91";
  if ($("lm_phone")) { $("lm_phone").placeholder = "10-digit mobile"; $("lm_phone").maxLength = 10; }
  $("leadModalTitle").textContent = lead ? "Edit Lead" : "New Lead";
  $("lm_id").value = lead ? lead.id : "";
  if (lead) {
    const cf = lead.custom_fields || {};
    const savedDial = cf.country_code || "+91";
    const _ce = (typeof LM_COUNTRIES !== "undefined" ? LM_COUNTRIES : []).find(x => x.d === savedDial);
    if ($("lm_country_code")) $("lm_country_code").value = savedDial;
    if ($("lm_country_label")) $("lm_country_label").textContent = `${_ce ? _ce.c : "IND"} ${savedDial}`;
    if ($("lm_phone")) { const _l = (typeof lmGetPhoneLen === "function" ? lmGetPhoneLen(savedDial) : null) || 10; $("lm_phone").maxLength = _l; $("lm_phone").placeholder = `${_l}-digit number`; }
    $("lm_full_name").value = `${lead.first_name || ""} ${lead.last_name || ""}`.trim();
    $("lm_phone").value = lead.phone || "";
    $("lm_email").value = lead.email || "";
    $("lm_city").value = cf.city || "";
    $("lm_location").value = cf.location || "";
    $("lm_current_profile").value = cf.current_profile || "";
    $("lm_highest_education").value = cf.highest_education || "";
    $("lm_notes").value = cf.notes || lead.notes || "";
    lmEnsureOption("lm_stage_id", lead.stage_id, lead.stage && lead.stage.name);
    lmEnsureOption("lm_owner_id", lead.owner_id, lead.owner && lead.owner.name);
    const savedSources = (cf.sources && cf.sources.length) ? cf.sources : (lead.source ? [lead.source] : []);
    document.querySelectorAll(".lm-source-check").forEach(cb => {
      cb.checked = savedSources.includes(cb.value);
    });
    lmRenderSourceLabel();
    if ($("lm_referral_name")) $("lm_referral_name").value = cf.referral_name || "";
    lmToggleReferralField();
    const savedProducts = (lead.products && lead.products.length) ? lead.products.map(p => String(p.id)) : (lead.product_id ? [String(lead.product_id)] : []);
    document.querySelectorAll(".lm-product-check").forEach(cb => {
      cb.checked = savedProducts.includes(cb.value);
    });
    lmRenderProductLabel();
    $("lm_stage_id").value = lead.stage_id || "";
    if ($("lm_owner_id")) $("lm_owner_id").value = lead.owner_id || "";
    $("lm_whatsapp").value = cf.whatsapp || "";
    $("lm_wa_same").checked = !!lead.phone && lead.phone === cf.whatsapp;
    (cf.extra_phones || []).forEach((p) => lmAddPhone(p));
  }
  syncWa();
  modal.classList.remove("hidden"); modal.classList.add("flex");
  // Sync the custom dropdown triggers to the values we just set programmatically.
  if (window.refreshDropdowns) window.refreshDropdowns(modal);
  lucide.createIcons();
  // Attach phone blur listener for duplicate checking
  attachPhoneBlurListener();
}
function closeLeadModal() { modal.classList.add("hidden"); modal.classList.remove("flex"); }
modal.addEventListener("click", (e) => { if (e.target === modal) closeLeadModal(); });

// Merge modal for duplicate M. Number
let mergeCheckDuplicate = null; // Store lead data when duplicate found
function closeMergeModal() {
  document.getElementById("mergeModal").classList.add("hidden");
  document.getElementById("mergeModal").classList.remove("flex");
}
function openMergeModal(lead) {
  mergeCheckDuplicate = lead;
  document.getElementById("mergeLeadName").textContent = lead.full_name;
  document.getElementById("mergeLeadPhone").textContent = lead.phone;
  document.getElementById("mergeLeadEmail").textContent = lead.email || "—";
  const productName = lead.product ? lead.product.name : "—";
  document.getElementById("mergeLeadProduct").textContent = productName;
  document.getElementById("mergeModal").classList.remove("hidden");
  document.getElementById("mergeModal").classList.add("flex");
}
function confirmMerge() {
  if (!mergeCheckDuplicate) return;
  closeMergeModal();
  // Load the existing lead into the modal for editing
  openLeadModal(mergeCheckDuplicate);
}
document.getElementById("mergeModal")?.addEventListener("click", (e) => {
  if (e.target.id === "mergeModal") closeMergeModal();
});

// Check for duplicate M. Number
async function checkDuplicatePhone() {
  const phone = $("lm_phone").value.trim();
  const currentLeadId = $("lm_id").value;

  if (!phone) {
    $("lm_phone_error").classList.add("hidden");
    return null;
  }

  const dial = ($("lm_country_code") && $("lm_country_code").value) || "+91";
  const expLen = (typeof lmGetPhoneLen === "function" ? lmGetPhoneLen(dial) : null) || 10;
  if (!new RegExp(`^\\d{${expLen}}$`).test(phone)) {
    $("lm_phone_error").textContent = `M. Number must be exactly ${expLen} digits`;
    $("lm_phone_error").classList.remove("hidden");
    return null;
  }

  $("lm_phone_error").classList.add("hidden");

  try {
    const result = await api(`leads?phone=${encodeURIComponent(phone)}`);
    const leads = (result && result.data) || [];
    const existing = leads.find(l => l.phone === phone && l.id != currentLeadId);
    return existing || null;
  } catch (err) {
    console.error("Error checking duplicate:", err);
    return null;
  }
}

// Add event listener for phone field blur when modal opens
function attachPhoneBlurListener() {
  const phoneField = $("lm_phone");
  if (phoneField) {
    phoneField.removeEventListener("blur", phoneBlurHandler);
    phoneField.addEventListener("blur", phoneBlurHandler);
  }
}

async function phoneBlurHandler() {
  const duplicate = await checkDuplicatePhone();
  if (duplicate && !$("lm_id").value) { // Only show merge for new leads
    openMergeModal(duplicate);
  }
}

$("leadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("lm_submit").disabled = true; $("lm_error").classList.add("hidden");
  const extra = [...document.querySelectorAll(".lm-extra")].map((i) => i.value.trim()).filter(Boolean);
  const cf = {};
  const put = (k, v) => { if (v) cf[k] = v; };
  put("city", $("lm_city").value);
  put("location", $("lm_location").value);
  put("current_profile", $("lm_current_profile").value);
  put("highest_education", $("lm_highest_education").value);
  put("whatsapp", $("lm_wa_same").checked ? $("lm_phone").value : $("lm_whatsapp").value);
  if (extra.length) cf.extra_phones = extra;
  put("notes", $("lm_notes").value);
  put("country_code", ($("lm_country_code") && $("lm_country_code").value) || "+91");
  put("referral_name", $("lm_referral_name") && $("lm_referral_name").value);

  const selectedSources = [...document.querySelectorAll(".lm-source-check:checked")].map(c => c.value);
  if (!selectedSources.length) {
    $("lm_error").textContent = "Select at least one source.";
    $("lm_error").classList.remove("hidden");
    $("lm_submit").disabled = false;
    return;
  }
  cf.sources = selectedSources;

  // Split the single "Full Name" field: first token is the first name, the rest the last name.
  const fullName = $("lm_full_name").value.trim().replace(/\s+/g, " ");
  const firstSpace = fullName.indexOf(" ");
  const firstName = firstSpace === -1 ? fullName : fullName.slice(0, firstSpace);
  const lastName = firstSpace === -1 ? "" : fullName.slice(firstSpace + 1);

  const selectedProducts = [...document.querySelectorAll(".lm-product-check:checked")].map(c => Number(c.value));

  const payload = {
    first_name: firstName, last_name: lastName,
    phone: $("lm_phone").value, source: selectedSources[0], custom_fields: cf,
  };
  if ($("lm_email").value) payload.email = $("lm_email").value;
  if (selectedProducts.length) {
    payload.product_id = selectedProducts[0];
    payload.products_id = selectedProducts;
  }
  if ($("lm_stage_id").value) payload.stage_id = Number($("lm_stage_id").value);
  if ($("lm_owner_id") && $("lm_owner_id").value) payload.owner_id = Number($("lm_owner_id").value);
  const id = $("lm_id").value;
  try {
    if (id) await api(`leads/${id}`, { method: "PUT", body: payload });
    else await api("leads", { method: "POST", body: payload });
    location.reload();
  } catch (err) {
    $("lm_error").textContent = err.data?.detail || err.data?.message || "Save failed.";
    $("lm_error").classList.remove("hidden");
  } finally { $("lm_submit").disabled = false; }
});
