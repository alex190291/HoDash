document.addEventListener("DOMContentLoaded", () => {
  // Expand/collapse detail-views on card click (unless a button is clicked)
  document.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.tagName.toLowerCase() === "button") return;
      const detailView = card.querySelector(".detail-view");
      if (detailView) {
        detailView.style.display =
          detailView.style.display === "" || detailView.style.display === "none"
            ? "block"
            : "none";
      }
    });
  });

  const modeToggle = document.getElementById("modeToggle");
  modeToggle.addEventListener("click", () => {
    document.body.classList.toggle("light-mode");
  });
});
