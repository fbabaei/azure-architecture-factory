// ============================================
// PRESENTATION SCRIPT
// ============================================

let presentationData = null;
let currentSlideIndex = 0;

/**
 * Initialize presentation on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Fetch presentation data
        const response = await fetch('/api/presentation-data');
        presentationData = await response.json();
        
        // Render slides
        renderSlides();
        
        // Update slide counter
        updateSlideCounter();
        
        // Setup keyboard navigation
        setupKeyboardNavigation();
        
        // Display first slide
        displaySlide(0);
        
        console.log('Presentation initialized with', presentationData.slides.length, 'slides');
    } catch (error) {
        console.error('Error initializing presentation:', error);
    }
});

/**
 * Render all slides
 */
function renderSlides() {
    if (!presentationData) return;
    
    const slidesContainer = document.getElementById('slides');
    slidesContainer.innerHTML = '';
    
    presentationData.slides.forEach((slide, index) => {
        const slideEl = document.createElement('div');
        slideEl.className = 'slide';
        if (index === 0) slideEl.classList.add('active');
        
        const metricsHTML = slide.metrics
            .map(metric => `<li>${metric}</li>`)
            .join('');
        
        slideEl.innerHTML = `
            <div class="slide-content">
                <div class="slide-number">${slide.number}/${presentationData.slides.length}</div>
                <h1 class="slide-title">${slide.title}</h1>
                <h2 class="slide-subtitle">${slide.content}</h2>
                <div class="slide-description"></div>
                <ul class="slide-metrics">
                    ${metricsHTML}
                </ul>
            </div>
        `;
        
        slidesContainer.appendChild(slideEl);
    });
}

/**
 * Display a specific slide
 */
function displaySlide(index) {
    if (!presentationData || index < 0 || index >= presentationData.slides.length) {
        return;
    }
    
    // Remove active class from all slides
    document.querySelectorAll('.slide').forEach(slide => {
        slide.classList.remove('active');
    });
    
    // Add active class to current slide
    const slides = document.querySelectorAll('.slide');
    slides[index].classList.add('active');
    
    // Update current index
    currentSlideIndex = index;
    
    // Update counter and buttons
    updateSlideCounter();
    updateNavButtons();
    updateProgressBar();
}

/**
 * Navigate to next slide
 */
function nextSlide() {
    if (currentSlideIndex < presentationData.slides.length - 1) {
        displaySlide(currentSlideIndex + 1);
    }
}

/**
 * Navigate to previous slide
 */
function previousSlide() {
    if (currentSlideIndex > 0) {
        displaySlide(currentSlideIndex - 1);
    }
}

/**
 * Update slide counter display
 */
function updateSlideCounter() {
    const current = document.getElementById('current-slide');
    const total = document.getElementById('total-slides');
    
    if (current && total && presentationData) {
        current.textContent = currentSlideIndex + 1;
        total.textContent = presentationData.slides.length;
    }
}

/**
 * Update navigation button states
 */
function updateNavButtons() {
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    
    if (prevBtn) {
        prevBtn.disabled = currentSlideIndex === 0;
    }
    
    if (nextBtn) {
        nextBtn.disabled = currentSlideIndex === presentationData.slides.length - 1;
    }
}

/**
 * Update progress bar
 */
function updateProgressBar() {
    const progressFill = document.getElementById('progress-fill');
    if (progressFill && presentationData) {
        const progress = ((currentSlideIndex + 1) / presentationData.slides.length) * 100;
        progressFill.style.width = progress + '%';
    }
}

/**
 * Setup keyboard navigation
 */
function setupKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
        switch (e.key) {
            case 'ArrowRight':
            case ' ':
                nextSlide();
                break;
            case 'ArrowLeft':
                previousSlide();
                break;
            case 'f':
            case 'F':
                toggleFullscreen();
                break;
            case 'Escape':
                exitFullscreen();
                break;
        }
    });
}

/**
 * Toggle fullscreen mode
 */
function toggleFullscreen() {
    const elem = document.documentElement;
    
    if (!document.fullscreenElement) {
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.msRequestFullscreen) {
            elem.msRequestFullscreen();
        }
    } else {
        exitFullscreen();
    }
}

/**
 * Exit fullscreen mode
 */
function exitFullscreen() {
    if (document.fullscreenElement) {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}

/**
 * Download presentation slide as PDF
 */
function downloadSlide() {
    const slide = document.querySelector('.slide.active');
    if (!slide) return;
    
    // For now, just print the current slide
    window.print();
    
    // TODO: Implement actual PDF download using PDF.js or similar
}

/**
 * Mouse wheel navigation
 */
document.addEventListener('wheel', (e) => {
    if (e.deltaY > 0) {
        nextSlide();
    } else {
        previousSlide();
    }
}, { passive: true });

/**
 * Touch swipe navigation
 */
let touchStartX = 0;
let touchEndX = 0;

document.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
}, false);

document.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
}, false);

function handleSwipe() {
    if (touchEndX < touchStartX - 50) {
        nextSlide();
    } else if (touchEndX > touchStartX + 50) {
        previousSlide();
    }
}

/**
 * Presenter notes (optional - for future enhancement)
 */
function getPresenterNotes(slideIndex) {
    const notes = {
        0: "Start with the problem statement. Emphasize how current processes take 4-8 weeks.",
        1: "Highlight business impact. Relate to specific costs and delays in their organization.",
        2: "Introduce the solution briefly. Set up for the detailed workflow.",
        3: "Walk through each phase. Emphasize automation and speed.",
        4: "Showcase real results and success metrics from actual deployments.",
        5: "Deep dive into key benefits. Let audience absorb each benefit.",
        6: "Show working reference implementation. This is proof of concept.",
        7: "Highlight use cases relevant to their industry.",
        8: "Present financial impact and ROI. This typically drives executive buy-in.",
        9: "End with clear next steps and call to action."
    };
    
    return notes[slideIndex] || '';
}

// Export functions for console debugging
window.debugPresentation = {
    currentSlide: () => currentSlideIndex,
    totalSlides: () => presentationData?.slides.length || 0,
    goToSlide: (index) => displaySlide(index),
    speaker: (index = currentSlideIndex) => getPresenterNotes(index)
};
