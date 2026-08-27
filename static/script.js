document.addEventListener('DOMContentLoaded', () => {
    const travelForm = document.getElementById('travel-form');
    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    const promptChips = document.querySelectorAll('.prompt-chip');

    const loadingSection = document.getElementById('loading-section');
    const progressBar = document.getElementById('progress-bar');
    const loadingSubtext = document.getElementById('loading-subtext');
    
    const errorCard = document.getElementById('error-card');
    const errorMessage = document.getElementById('error-message');

    const resultsSection = document.getElementById('results-section');
    const resThreadId = document.getElementById('res-thread-id');
    const resLlmCalls = document.getElementById('res-llm-calls');
    
    const masterPlanOutput = document.getElementById('master-plan-output');
    const flightOutput = document.getElementById('flight-output');
    const hotelOutput = document.getElementById('hotel-output');
    const itineraryOutput = document.getElementById('itinerary-output');

    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    const copyBtn = document.getElementById('copy-btn');
    const resetBtn = document.getElementById('reset-btn');
    const toast = document.getElementById('toast');

    let currentThreadId = localStorage.getItem('tripmint_thread_id') || null;

    // Handle Quick Prompt Chips
    promptChips.forEach(chip => {
        chip.addEventListener('click', () => {
            queryInput.value = chip.getAttribute('data-prompt');
            queryInput.focus();
        });
    });

    // Handle Tab Switches
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
        });
    });

    // Form Submission
    travelForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userQuery = queryInput.value.trim();

        if (!userQuery) return;

        // Reset UI
        hideElement(errorCard);
        hideElement(resultsSection);
        showElement(loadingSection);
        submitBtn.disabled = true;

        // Animate Progress & Steps
        simulateProgress();

        try {
            const response = await fetch('/api/travel_planner', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: userQuery,
                    thread_id: currentThreadId
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate trip plan.');
            }

            // Save thread_id for conversation continuity
            if (data.thread_id) {
                currentThreadId = data.thread_id;
                localStorage.setItem('tripmint_thread_id', currentThreadId);
            }

            // Populate Results
            renderResults(data);

        } catch (err) {
            errorMessage.textContent = err.message || 'An unexpected error occurred.';
            showElement(errorCard);
        } finally {
            hideElement(loadingSection);
            submitBtn.disabled = false;
        }
    });

    // Copy Plan Button
    copyBtn.addEventListener('click', () => {
        const textToCopy = masterPlanOutput.innerText;
        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('Trip plan copied to clipboard!');
        });
    });

    // Reset Search Button
    resetBtn.addEventListener('click', () => {
        queryInput.value = '';
        hideElement(resultsSection);
        hideElement(errorCard);
        queryInput.focus();
    });

    // Helper Functions
    function renderResults(data) {
        resThreadId.textContent = data.thread_id ? data.thread_id.substring(0, 12) + '...' : '-';
        resLlmCalls.textContent = data.llm_calls || 0;

        // Render Markdown for Master Plan and Itinerary
        masterPlanOutput.innerHTML = typeof marked !== 'undefined' ? marked.parse(data.answer) : data.answer;
        itineraryOutput.innerHTML = typeof marked !== 'undefined' ? marked.parse(data.itinerary) : data.itinerary;

        // Raw text for Flight and Hotel tabs
        flightOutput.textContent = data.flight_results || 'No flight data available.';
        hotelOutput.textContent = data.hotel_results || 'No hotel recommendations available.';

        showElement(resultsSection);
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function simulateProgress() {
        const steps = [
            { id: 'step-flight', text: 'Executing flight_agent (fetching live flights)...', progress: '25%' },
            { id: 'step-hotel', text: 'Executing hotel_agent (searching top hotels)...', progress: '50%' },
            { id: 'step-itinerary', text: 'Executing itinerary_agent (building day-by-day plan)...', progress: '75%' },
            { id: 'step-master', text: 'Executing master_agent (synthesizing final answer)...', progress: '95%' }
        ];

        let index = 0;
        document.querySelectorAll('.step-item').forEach(s => s.className = 'step-item');

        const interval = setInterval(() => {
            if (index < steps.length) {
                const current = steps[index];
                loadingSubtext.textContent = current.text;
                progressBar.style.width = current.progress;

                const stepEl = document.getElementById(current.id);
                if (stepEl) stepEl.classList.add('active');

                if (index > 0) {
                    const prevEl = document.getElementById(steps[index - 1].id);
                    if (prevEl) {
                        prevEl.classList.remove('active');
                        prevEl.classList.add('completed');
                    }
                }
                index++;
            } else {
                clearInterval(interval);
            }
        }, 1200);
    }

    function showToast(msg) {
        toast.textContent = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3000);
    }

    function showElement(el) { el.classList.remove('hidden'); }
    function hideElement(el) { el.classList.add('hidden'); }
});
