function updateDockerTable(dockerData) {
  const dockerDataEl = document.getElementById("docker-data");
  dockerDataEl.innerHTML = (dockerData || [])
    .map((cont) => {
      let statusClass;
      const lowerStatus = cont.status ? cont.status.toLowerCase() : "";

      if (lowerStatus.includes("update success")) {
        statusClass = "status-green";
      } else if (/^updat/i.test(lowerStatus)) {
        statusClass = "status-yellow";
        if (lowerStatus.includes("failed")) {
          statusClass = "status-red";
        }
      } else if (!cont.up_to_date) {
        statusClass = "status-blue";
      } else if (lowerStatus.includes("running")) {
        statusClass = "status-green";
      } else if (
        lowerStatus.includes("starting") ||
        lowerStatus.includes("created")
      ) {
        statusClass = "status-yellow";
      } else {
        statusClass = "status-red";
      }

      const hrs = Math.floor(cont.uptime / 3600);
      const mins = Math.floor((cont.uptime % 3600) / 60);

      let updateBtn = "";
      if (!cont.up_to_date && !/updating/i.test(cont.status)) {
        updateBtn = `<button class="update-btn" onclick="updateContainer('${cont.name}')">↑ Update</button>`;
      }

      return `<tr>
                <td><div class="status-indicator ${statusClass}"></div></td>
                <td>${cont.name}</td>
                <td>${hrs}h ${mins}m</td>
                <td>${cont.image}</td>
                <td>${updateBtn}</td>
            </tr>`;
    })
    .join("");
}
