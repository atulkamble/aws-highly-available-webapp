"use strict";

const fields = {
  instance: document.getElementById("instance-id"),
  zone: document.getElementById("availability-zone"),
  region: document.getElementById("region"),
  uptime: document.getElementById("uptime"),
  requests: document.getElementById("page-requests"),
  version: document.getElementById("app-version"),
  status: document.getElementById("app-status"),
  health: document.getElementById("application-health"),
};

function formatUptime(totalSeconds) {
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts = [];
  if (days) parts.push(`${days}d`);
  if (hours || days) parts.push(`${hours}h`);
  if (minutes || hours || days) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);
  return parts.join(" ");
}

function updateCountdown() {
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const remainingSeconds = Math.max(0, Math.floor((midnight - now) / 1000));
  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const seconds = remainingSeconds % 60;
  document.getElementById("countdown-hours").textContent = String(hours).padStart(2, "0");
  document.getElementById("countdown-minutes").textContent = String(minutes).padStart(2, "0");
  document.getElementById("countdown-seconds").textContent = String(seconds).padStart(2, "0");
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`Status endpoint returned ${response.status}`);
    const status = await response.json();

    fields.instance.textContent = status.instance_id;
    fields.zone.textContent = status.availability_zone;
    fields.region.textContent = status.region;
    fields.uptime.textContent = formatUptime(status.uptime_seconds);
    fields.requests.textContent = status.page_requests.toLocaleString();
    fields.version.textContent = status.app_version;
    fields.status.textContent = "Event registration open";
    fields.health.textContent = "Application status: online";
  } catch (_error) {
    fields.status.textContent = "Event registration open";
    fields.health.textContent = "Application status: status unavailable";
  }
}

const registrationForm = document.getElementById("registration-form");
const registrationMessage = document.getElementById("registration-message");

registrationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = registrationForm.querySelector("button[type='submit']");
  const formData = new FormData(registrationForm);
  const registration = Object.fromEntries(formData.entries());
  submitButton.disabled = true;
  registrationMessage.classList.remove("is-error");
  registrationMessage.textContent = "Submitting your registration…";

  try {
    const response = await fetch("/api/register", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(registration),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Registration could not be completed.");
    registrationMessage.textContent = result.message;
    registrationForm.reset();
  } catch (error) {
    registrationMessage.classList.add("is-error");
    registrationMessage.textContent = error.message || "Unable to submit your registration. Please try again.";
  } finally {
    submitButton.disabled = false;
  }
});

updateCountdown();
window.setInterval(updateCountdown, 1000);
refreshStatus();
window.setInterval(refreshStatus, 5000);
