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

const backgroundVideo = document.querySelector(".background-video");
const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

function syncBackgroundVideo() {
  if (motionPreference.matches) {
    backgroundVideo.pause();
    return;
  }
  backgroundVideo.play().catch(() => {
    backgroundVideo.hidden = true;
  });
}

motionPreference.addEventListener("change", syncBackgroundVideo);
syncBackgroundVideo();

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
    fields.status.textContent = "Application online";
    fields.health.textContent = "Healthy";
  } catch (_error) {
    fields.status.textContent = "Status unavailable";
    fields.health.textContent = "Retrying";
  }
}

refreshStatus();
window.setInterval(refreshStatus, 5000);
