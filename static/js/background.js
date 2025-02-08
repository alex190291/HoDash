function generateHexagons(count) {
  const container = document.getElementById("hexagon-container");
  for (let i = 0; i < count; i++) {
    const hex = document.createElement("div");
    hex.classList.add("hexagon");
    const top = randomInt(0, 100);
    const left = randomInt(0, 100);
    const size = randomInt(80, 250);
    const delay = randomFloat(0, 10).toFixed(1);
    hex.style.top = top + "%";
    hex.style.left = left + "%";
    hex.style.width = size + "px";
    hex.style.height = size + "px";
    hex.style.animationDelay = delay + "s";
    container.appendChild(hex);
  }
}
