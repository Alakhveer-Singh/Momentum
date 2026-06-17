// Shared New/Edit Lead modal. Submits to DRF /api (POST create, PUT update).
const $ = (id) => document.getElementById(id);
const modal = $("leadModal");

function lmAddPhone(val = "") {
  const wrap = document.createElement("div");
  wrap.className = "mt-2 flex gap-2";
  wrap.innerHTML = `<input type="tel" class="lm-inp lm-extra" placeholder="Additional mobile" value="${val}" />
    <button type="button" class="shrink-0 rounded-lg p-2 text-red-400 hover:bg-red-50"><i data-lucide="x" class="h-4 w-4"></i></button>`;
  wrap.querySelector("button").onclick = () => wrap.remove();
  $("lm_extra_phones").appendChild(wrap);
  lucide.createIcons();
}

function syncWa() {
  const same = $("lm_wa_same").checked;
  $("lm_whatsapp").style.display = same ? "none" : "block";
  if (same) $("lm_whatsapp").value = $("lm_phone").value;
}
document.addEventListener("change", (e) => { if (e.target.id === "lm_wa_same") syncWa(); });
document.addEventListener("input", (e) => { if (e.target.id === "lm_phone" && $("lm_wa_same").checked) $("lm_whatsapp").value = e.target.value; });

function openLeadModal(lead = null) {
  $("leadForm").reset();
  $("lm_extra_phones").innerHTML = "";
  $("lm_error").classList.add("hidden");
  $("leadModalTitle").textContent = lead ? "Edit Lead" : "New Lead";
  $("lm_id").value = lead ? lead.id : "";
  if (lead) {
    const cf = lead.custom_fields || {};
    $("lm_first_name").value = lead.first_name || "";
    $("lm_last_name").value = lead.last_name || "";
    $("lm_phone").value = lead.phone || "";
    $("lm_email").value = lead.email || "";
    $("lm_city").value = cf.city || "";
    $("lm_location").value = cf.location || "";
    $("lm_current_profile").value = cf.current_profile || "";
    $("lm_highest_education").value = cf.highest_education || "";
    $("lm_notes").value = cf.notes || lead.notes || "";
    $("lm_source").value = lead.source || "";
    $("lm_stage_id").value = lead.stage_id || "";
    if ($("lm_owner_id")) $("lm_owner_id").value = lead.owner_id || "";
    $("lm_whatsapp").value = cf.whatsapp || "";
    $("lm_wa_same").checked = !!lead.phone && lead.phone === cf.whatsapp;
    (cf.extra_phones || []).forEach((p) => lmAddPhone(p));
  }
  syncWa();
  modal.classList.remove("hidden"); modal.classList.add("flex");
  lucide.createIcons();
}
function closeLeadModal() { modal.classList.add("hidden"); modal.classList.remove("flex"); }
modal.addEventListener("click", (e) => { if (e.target === modal) closeLeadModal(); });

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

  const phoneVal = $("lm_phone").dataset.formatted || $("lm_phone").value;
  const payload = {
    first_name: $("lm_first_name").value, last_name: $("lm_last_name").value,
    phone: phoneVal, source: $("lm_source").value, custom_fields: cf,
  };
  if ($("lm_email").value) payload.email = $("lm_email").value;
  if ($("lm_stage_id").value) payload.stage_id = Number($("lm_stage_id").value);
  if ($("lm_owner_id") && $("lm_owner_id").value) payload.owner_id = Number($("lm_owner_id").value);
  const id = $("lm_id").value;
  try {
    if (id) await api(`leads/${id}`, { method: "PUT", body: payload });
    else await api("leads", { method: "POST", body: payload });
    location.reload();
  } catch (err) {
    $("lm_error").textContent = err.data?.message || "Save failed.";
    $("lm_error").classList.remove("hidden");
  } finally { $("lm_submit").disabled = false; }
});
