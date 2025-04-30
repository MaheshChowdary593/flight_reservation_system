const themeBtn = document.getElementById("themeToggle");
const themeLink = document.getElementById("themeStylesheet");

themeBtn.onclick = () => {
  const currentTheme = themeLink.getAttribute("href");

  if (currentTheme === "style2.css") {
    themeLink.setAttribute("href", "style.css"); // switch to dark
    themeBtn.textContent = "🌞"; // show sun
  } else {
    themeLink.setAttribute("href", "style2.css"); // switch to light
    themeBtn.textContent = "🌙"; // show moon
  }
};