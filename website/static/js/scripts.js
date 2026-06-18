// ================================
// Mobile menu toggle
// ================================
function toggleMenu() {
    const navbar = document.getElementById("navbar");
    navbar.classList.toggle("show");
}

// ================================
// FAQ accordion toggle
// ================================
function toggleFaq(btn) {
    const item = btn.parentElement;
    const isOpen = item.classList.contains("open");

    document.querySelectorAll(".faq-item").forEach(i => {
        i.classList.remove("open");
    });

    if (!isOpen) {
        item.classList.add("open");
    }
}

// ================================
// Back to top button
// ================================
window.addEventListener("scroll", () => {
    const btn = document.querySelector(".back-to-top");
    if (btn) {
        btn.style.opacity = window.scrollY > 300 ? "1" : "0";
    }
});

document.querySelector(".back-to-top")?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
});

// ================================
// Hero Slider (Coca-Cola style)
// ================================
document.addEventListener("DOMContentLoaded", function () {
    const slides = document.querySelectorAll(".hero-slide");
    const dotsContainer = document.getElementById("heroDots");
    const prevBtn = document.getElementById("heroPrev");
    const nextBtn = document.getElementById("heroNext");

    if (!slides.length) return;

    let current = 0;
    let interval;

    // Build dots
    slides.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.classList.add("hero-dot");
        if (i === 0) dot.classList.add("active");
        dot.addEventListener("click", () => {
            goToSlide(i);
            resetInterval();
        });
        dotsContainer.appendChild(dot);
    });

    const dots = document.querySelectorAll(".hero-dot");

    // Hide controls if only one slide
    if (slides.length <= 1) {
        if (dotsContainer) dotsContainer.style.display = "none";
        if (prevBtn) prevBtn.style.display = "none";
        if (nextBtn) nextBtn.style.display = "none";
        return;
    }

    function goToSlide(index) {
        slides[current].classList.remove("active");
        dots[current].classList.remove("active");
        current = (index + slides.length) % slides.length;
        slides[current].classList.add("active");
        dots[current].classList.add("active");
    }

    function nextSlide() { goToSlide(current + 1); }
    function prevSlide() { goToSlide(current - 1); }

    if (nextBtn) nextBtn.addEventListener("click", () => { nextSlide(); resetInterval(); });
    if (prevBtn) prevBtn.addEventListener("click", () => { prevSlide(); resetInterval(); });

    function resetInterval() {
        clearInterval(interval);
        interval = setInterval(nextSlide, 5000);
    }

    interval = setInterval(nextSlide, 5000);
});