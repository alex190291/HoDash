function pollContainerUpdate(containerName, button) {
  const pollInt = setInterval(() => {
    fetch(`/update_status/${containerName}`)
      .then((r) => r.json())
      .then((st) => {
        if (st.in_progress && !st.error) {
          if (!button.dataset.startedUpdate) {
            setButtonColor(button, "yellow");
            button.dataset.startedUpdate = "true";
          }
          button.innerHTML = `${st.phase} <div class="spinner"></div>`;
          return;
        }
        clearInterval(pollInt);

        if (st.error) {
          setButtonColor(button, "red");
          button.innerHTML = "Update failed";
          button.disabled = false;
        } else if (st.success) {
          setButtonColor(button, "#33cc33");
          button.innerHTML = "Updated successfully";
          button.disabled = true;
          setTimeout(() => {
            setButtonColor(button, "var(--primary)");
            button.style.display = "none";
            button.disabled = false;
          }, 10000);
        }
        updateStats();
      })
      .catch((err) => {
        console.error("Error polling update status:", err);
        clearInterval(pollInt);
      });
  }, 1000);
}

function updateContainer(containerName) {
  const btn = event.target;
  if (btn.innerHTML.toLowerCase().includes("failed")) {
    setButtonColor(btn, "var(--primary)");
  }
  btn.innerHTML = `initializing... <div class="spinner"></div>`;
  btn.disabled = true;

  fetch(`/update_container/${containerName}`, { method: "POST" })
    .then((r) => r.json())
    .then(() => {
      pollContainerUpdate(containerName, btn);
    })
    .catch((err) => {
      console.error("Error updating container:", err);
    });
}

let checkAllInterval = null;
function checkAllUpdates() {
  const btn = document.getElementById("checkAllBtn");
  btn.disabled = true;
  btn.innerHTML = `↻ Check for updates <div class="spinner"></div>`;

  fetch("/check_all", { method: "POST" })
    .then((r) => r.json())
    .then((d) => {
      if (d.status !== "already_in_progress") {
        checkAllInterval = setInterval(pollCheckAllStatus, 500);
      } else {
        btn.innerHTML = "↻ Check for updates";
        btn.disabled = false;
      }
    })
    .catch((err) => {
      console.error("Error starting check_all:", err);
      btn.disabled = false;
      btn.innerHTML = "↻ Check for updates";
    });
}

function pollCheckAllStatus() {
  const btn = document.getElementById("checkAllBtn");
  fetch("/check_all_status")
    .then((r) => r.json())
    .then((st) => {
      if (st.in_progress) {
        btn.innerHTML = `Checking... (${st.checked}/${st.total})`;
      } else {
        btn.innerHTML = "↻ Check for updates";
        btn.disabled = false;
        clearInterval(checkAllInterval);
        checkAllInterval = null;
        updateStats();
      }
    })
    .catch((err) => console.error("Error polling check_all status:", err));
}
