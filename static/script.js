document.addEventListener('DOMContentLoaded', () => {
    const travelForm = document.getElementById('travel-form');
    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    const promptChips = document.querySelectorAll('.prompt-chip');

    const loadingSection = document.getElementById('loading-section');
    const progressBar = document.getElementById('progress-bar');
    const loadingSubtext = document.getElementById('loading-subtext') || document.getElementById('loading-step');
    
    const approvalCard = document.getElementById('approval-card');
    const draftItineraryPreview = document.getElementById('draft-itinerary-preview');
    const approvalFeedbackInput = document.getElementById('approval-feedback-input');
    const btnApprove = document.getElementById('btn-approve');
    const btnRevise = document.getElementById('btn-revise');

    const errorCard = document.getElementById('error-card');
    const errorMessage = document.getElementById('error-message');

    const resultsSection = document.getElementById('results-section');
    const resThreadId = document.getElementById('res-thread-id');
    const resLlmCalls = document.getElementById('res-llm-calls');
    const resAgentsText = document.getElementById('res-agents-text');
    
    const masterPlanOutput = document.getElementById('master-plan-output');
    const flightOutput = document.getElementById('flight-output');
    const hotelOutput = document.getElementById('hotel-output');
    const weatherOutput = document.getElementById('weather-output');
    const budgetOutput = document.getElementById('budget-output');
    const itineraryOutput = document.getElementById('itinerary-output');

    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    const copyBtn = document.getElementById('copy-btn');
    const resetBtn = document.getElementById('reset-btn');
    const toast = document.getElementById('toast');

    let currentThreadId = localStorage.getItem('tripmint_thread_id') || null;
    // Dynamic Auto-Resizing Textarea without internal scrollbars
    function autoResizeTextarea(textarea) {
        if (!textarea) return;
        textarea.style.height = 'auto';
        const computedHeight = Math.max(56, textarea.scrollHeight);
        textarea.style.height = computedHeight + 'px';
    }

    if (queryInput) {
        queryInput.addEventListener('input', () => autoResizeTextarea(queryInput));
        queryInput.addEventListener('change', () => autoResizeTextarea(queryInput));
        setTimeout(() => autoResizeTextarea(queryInput), 60);
    }

    // Handle Quick Prompt Chips
    promptChips.forEach(chip => {
        chip.addEventListener('click', () => {
            queryInput.value = chip.getAttribute('data-prompt');
            autoResizeTextarea(queryInput);
            queryInput.focus();
        });
    });

    // Enter key submits form from textarea (Shift+Enter creates a newline)
    if (queryInput) {
        queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (typeof travelForm.requestSubmit === 'function') {
                    travelForm.requestSubmit();
                } else {
                    travelForm.dispatchEvent(new Event('submit', { cancelable: true }));
                }
            }
        });
    }

    // Handle Destination Showcase Cards
    const destinationCards = document.querySelectorAll('.destination-card, .destination-trio-card');
    destinationCards.forEach(card => {
        card.addEventListener('click', () => {
            const prompt = card.getAttribute('data-prompt');
            if (prompt) {
                queryInput.value = prompt;
                autoResizeTextarea(queryInput);
                queryInput.focus();
                queryInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    });

    // Handle Tab Switches
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const contentEl = document.getElementById(targetTab);
            if (contentEl) contentEl.classList.add('active');
        });
    });

    // Helper to read and dispatch Server-Sent Events (SSE)
    async function readSseStream(response, onEvent) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split('\n\n');
            buffer = parts.pop() || '';

            for (const part of parts) {
                if (!part.trim()) continue;
                let eventType = 'message';
                let dataStr = '';

                const lines = part.split('\n');
                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        eventType = line.replace('event:', '').trim();
                    } else if (line.startsWith('data:')) {
                        dataStr += line.replace('data:', '').trim();
                    }
                }

                if (dataStr) {
                    try {
                        const parsedData = JSON.parse(dataStr);
                        onEvent(eventType, parsedData);
                    } catch (err) {
                        console.error('Error parsing SSE JSON:', err, dataStr);
                    }
                }
            }
        }
    }

    function setStepActive(id, text = null, progress = null) {
        const el = document.getElementById(id);
        if (el) {
            el.classList.remove('completed');
            el.classList.add('active');
        }
        if (text && loadingSubtext) loadingSubtext.textContent = text;
        if (progress && progressBar) progressBar.style.width = progress;
    }

    function setStepCompleted(id) {
        const el = document.getElementById(id);
        if (el) {
            el.classList.remove('active');
            el.classList.add('completed');
        }
    }

    // Form Submission with SSE Streaming
    travelForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userQuery = queryInput.value.trim();

        if (!userQuery) return;

        // Reset UI
        hideElement(errorCard);
        hideElement(resultsSection);
        hideElement(approvalCard);
        showElement(loadingSection);
        submitBtn.disabled = true;

        // Auto-scroll down smoothly to the output/loading section immediately
        loadingSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        document.querySelectorAll('.step-item').forEach(s => s.className = 'step-item');
        setStepActive('step-supervisor', 'Connecting to TripMint AI stream...', '10%');

        currentThreadId = null;
        localStorage.removeItem('tripmint_thread_id');

        try {
            const response = await fetch('/api/travel_planner/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: userQuery,
                    thread_id: null
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server returned status ${response.status}`);
            }

            let receivedInterrupt = false;
            let receivedComplete = false;

            await readSseStream(response, (event, data) => {
                if (event === 'start') {
                    if (data.thread_id) {
                        currentThreadId = data.thread_id;
                        localStorage.setItem('tripmint_thread_id', currentThreadId);
                    }
                    setStepActive('step-supervisor', '🛡️ Validating Guardrail & Extracting Trip Constraints...', '20%');
                } else if (event === 'node_complete') {
                    const node = data.node;
                    const update = data.update || {};

                    if (node === 'supervisor_agent') {
                        setStepCompleted('step-supervisor');
                        const selected = update.selected_agents || [];
                        const specialists = selected.filter(s => s !== 'itinerary_agent');

                        if (specialists.length > 0) {
                            specialists.forEach(spec => {
                                const stepKey = spec.replace('_agent', '');
                                setStepActive('step-' + stepKey);
                            });
                            setStepActive(null, `🚀 Parallel Fan-Out: Running ${specialists.map(s => s.replace('_agent', '')).join(', ')} concurrently...`, '50%');
                        } else {
                            setStepActive('step-itinerary', 'Generating Day-by-Day Itinerary...', '60%');
                        }
                    } else if (node === 'flight_agent') {
                        setStepCompleted('step-flight');
                    } else if (node === 'hotel_agent') {
                        setStepCompleted('step-hotel');
                    } else if (node === 'weather_agent') {
                        setStepCompleted('step-weather');
                    } else if (node === 'budget_agent') {
                        setStepCompleted('step-budget');
                    } else if (node === 'itinerary_agent') {
                        setStepCompleted('step-itinerary');
                        setStepActive('step-itinerary', 'Itinerary draft ready for review.', '85%');
                    } else if (node === 'guardrail_blocked') {
                        setStepCompleted('step-supervisor');
                    }
                } else if (event === 'interrupt') {
                    receivedInterrupt = true;
                    handleInterrupt(data);
                } else if (event === 'complete') {
                    receivedComplete = true;
                    renderResults(data);
                }
            });

            if (!receivedInterrupt && !receivedComplete) {
                throw new Error('Stream ended without receiving final response or interrupt.');
            }

        } catch (err) {
            errorMessage.textContent = err.message || 'An unexpected error occurred.';
            showElement(errorCard);
        } finally {
            hideElement(loadingSection);
            submitBtn.disabled = false;
        }
    });

    // Handle Human In The Loop Approval
    function handleInterrupt(data) {
        hideElement(loadingSection);
        hideElement(resultsSection);
        showElement(approvalCard);

        if (data.thread_id) {
            currentThreadId = data.thread_id;
            localStorage.setItem('tripmint_thread_id', currentThreadId);
        }

        const draftContent = data.itinerary || data.answer || 'Draft itinerary ready for review.';
        draftItineraryPreview.innerHTML = renderInteractiveItinerary(draftContent, 'draft');
        approvalFeedbackInput.value = '';
        approvalCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Approve Button Action
    btnApprove.addEventListener('click', () => {
        const feedback = approvalFeedbackInput.value.trim();
        submitApproval(true, feedback);
    });

    // Revise Button Action
    btnRevise.addEventListener('click', () => {
        const feedback = approvalFeedbackInput.value.trim();
        if (!feedback) {
            alert('Please provide feedback or suggestions for the revision.');
            approvalFeedbackInput.focus();
            return;
        }
        submitApproval(false, feedback);
    });

    // Submit Approval with SSE Streaming
    async function submitApproval(approved, feedback) {
        if (!currentThreadId) {
            currentThreadId = localStorage.getItem('tripmint_thread_id');
        }

        if (!currentThreadId) {
            errorMessage.textContent = 'Session thread ID not found. Please submit your travel request again.';
            showElement(errorCard);
            return;
        }

        hideElement(approvalCard);
        hideElement(errorCard);
        showElement(loadingSection);

        // Update step indicators visually
        const stepIds = ['step-supervisor', 'step-flight', 'step-hotel', 'step-weather', 'step-budget', 'step-itinerary'];
        stepIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.classList.remove('active');
                el.classList.add('completed');
            }
        });
        setStepActive('step-master', approved 
            ? 'User approved draft. Master Agent synthesizing comprehensive final plan...' 
            : 'Applying feedback and revising travel plan...', '88%');

        btnApprove.disabled = true;
        btnRevise.disabled = true;

        try {
            const response = await fetch('/api/resume_planner/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    thread_id: currentThreadId,
                    approved: approved,
                    feedback: feedback
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server returned status ${response.status}`);
            }

            await readSseStream(response, (event, data) => {
                if (event === 'node_complete') {
                    if (data.node === 'master_agent') {
                        setStepCompleted('step-master');
                        if (progressBar) progressBar.style.width = '100%';
                    }
                } else if (event === 'complete') {
                    renderResults(data);
                }
            });

        } catch (err) {
            errorMessage.textContent = err.message || 'Error processing approval.';
            showElement(errorCard);
        } finally {
            btnApprove.disabled = false;
            btnRevise.disabled = false;
            hideElement(loadingSection);
        }
    }

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
        autoResizeTextarea(queryInput);
        currentThreadId = null;
        localStorage.removeItem('tripmint_thread_id');
        hideElement(resultsSection);
        hideElement(approvalCard);
        hideElement(errorCard);
        queryInput.focus();
    });

    // Helper Functions
    function renderResults(data) {
        hideElement(approvalCard);
        resThreadId.textContent = data.thread_id ? data.thread_id.substring(0, 12) + '...' : '-';
        resLlmCalls.textContent = data.llm_calls || 0;

        // Check if request was flagged as harmful or blocked by the safety guardrail
        const isHarmfulOrBlocked = (data.guardrail_allowed === false) ||
            (data.selected_agents && data.selected_agents.length === 0 && data.answer) ||
            (data.guardrail_reason && data.guardrail_reason.length > 0 && (!data.selected_agents || data.selected_agents.length === 0)) ||
            (data.answer && (
                data.answer.toLowerCase().includes('guardrail blocked') ||
                data.answer.toLowerCase().includes('blocked by the guardrail') ||
                data.answer.toLowerCase().includes('only help with travel') ||
                data.answer.toLowerCase().includes('harmful') ||
                data.answer.toLowerCase().includes('safety policy')
            ));

        if (isHarmfulOrBlocked) {
            resAgentsText.innerHTML = '<span class="status-harmful-badge"><i class="fa-solid fa-triangle-exclamation"></i> Safety Guardrail (Blocked)</span>';
            const harmfulMessage = data.guardrail_reason || data.answer || 'TripMint AI can only process lawful travel-planning queries. This request was blocked by the safety guardrail.';
            
            masterPlanOutput.innerHTML = `
                <div class="harmful-alert-box">
                    <div class="harmful-alert-header">
                        <i class="fa-solid fa-circle-xmark"></i>
                        <span>SAFETY POLICY TRIGGERED · HARMFUL / OFF-TOPIC REQUEST BLOCKED</span>
                    </div>
                    <div class="harmful-alert-body">
                        ${escapeHtml(harmfulMessage)}
                    </div>
                    <div class="harmful-alert-footer">
                        <i class="fa-solid fa-shield-halved"></i> TripMint AI is strictly governed to plan safe, lawful vacations, flights, hotels, weather forecasts, and itineraries.
                    </div>
                </div>
            `;

            // Hide specialist tabs since they were blocked
            ['tab-btn-flights', 'tab-btn-hotels', 'tab-btn-weather', 'tab-btn-budget', 'tab-btn-itinerary'].forEach(id => {
                const b = document.getElementById(id);
                if (b) b.style.display = 'none';
            });
            const masterBtn = document.getElementById('tab-btn-master');
            if (masterBtn) {
                masterBtn.style.display = 'inline-flex';
                masterBtn.click();
            }

            showElement(resultsSection);
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

        if (data.selected_agents && data.selected_agents.length > 0) {
            resAgentsText.textContent = data.selected_agents.join(' ➔ ');
        } else {
            resAgentsText.textContent = 'All Agents';
        }

        // Render Markdown fields with interactive day sub-tabs & clean white UI
        masterPlanOutput.innerHTML = renderStructuredMasterPlan(data.answer || '');
        itineraryOutput.innerHTML = renderInteractiveItinerary(data.itinerary || 'No itinerary available.', 'detailed');
        flightOutput.innerHTML = formatSegmentContent(data.flight_results || 'No flight data available.', 'flights');
        hotelOutput.innerHTML = formatSegmentContent(data.hotel_results || 'No hotel recommendations available.', 'hotels');
        weatherOutput.innerHTML = formatSegmentContent(data.weather_result || 'No weather data available.', 'weather');
        budgetOutput.innerHTML = formatSegmentContent(data.budget_analysis || 'No budget data available.', 'budget');

        // Dynamic Tab Visibility: only display tabs for agents that were selected and executed
        const selected = Array.isArray(data.selected_agents) ? data.selected_agents : [];

        const tabSpecs = [
            { btn: document.getElementById('tab-btn-master'), content: document.getElementById('tab-master'), show: true },
            { btn: document.getElementById('tab-btn-flights'), content: document.getElementById('tab-flights'), show: selected.includes('flight_agent') && Boolean(data.flight_results && !data.flight_results.startsWith('Unable to fetch flight data')) },
            { btn: document.getElementById('tab-btn-hotels'), content: document.getElementById('tab-hotels'), show: selected.includes('hotel_agent') && Boolean(data.hotel_results && !data.hotel_results.startsWith('Unable to fetch hotel')) },
            { btn: document.getElementById('tab-btn-weather'), content: document.getElementById('tab-weather'), show: selected.includes('weather_agent') && Boolean(data.weather_result && !data.weather_result.startsWith('Error fetching weather') && !data.weather_result.startsWith('No specific destination')) },
            { btn: document.getElementById('tab-btn-budget'), content: document.getElementById('tab-budget'), show: selected.includes('budget_agent') && Boolean(data.budget_analysis) },
            { btn: document.getElementById('tab-btn-itinerary'), content: document.getElementById('tab-itinerary'), show: (selected.includes('itinerary_agent') || selected.length === 0) && Boolean(data.itinerary) }
        ];

        let firstVisibleBtn = null;

        tabSpecs.forEach(t => {
            if (t.show) {
                if (t.btn) t.btn.style.display = 'inline-flex';
                if (!firstVisibleBtn && t.btn) {
                    firstVisibleBtn = t.btn;
                }
            } else {
                if (t.btn) {
                    t.btn.style.display = 'none';
                    t.btn.classList.remove('active');
                }
                if (t.content) {
                    t.content.classList.remove('active');
                }
            }
        });

        // Activate the first visible tab
        if (firstVisibleBtn) {
            firstVisibleBtn.click();
        }

        showElement(resultsSection);
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function simulateProgress() {
        const steps = [
            { id: 'step-supervisor', text: 'Validating Guardrail & selecting specialist agents...', progress: '15%' },
            { id: 'step-flight', text: 'Executing flight_agent (fetching live flights)...', progress: '30%' },
            { id: 'step-hotel', text: 'Executing hotel_agent (searching top hotels via Tavily)...', progress: '48%' },
            { id: 'step-weather', text: 'Executing weather_agent (fetching weather forecast)...', progress: '64%' },
            { id: 'step-budget', text: 'Executing budget_agent (analyzing feasibility & costs)...', progress: '78%' },
            { id: 'step-itinerary', text: 'Executing itinerary_agent (building day-by-day plan)...', progress: '90%' },
            { id: 'step-master', text: 'Synthesizing final plan...', progress: '98%' }
        ];

        let index = 0;
        document.querySelectorAll('.step-item').forEach(s => s.className = 'step-item');
        progressBar.style.width = '5%';

        if (progressInterval) clearInterval(progressInterval);

        progressInterval = setInterval(() => {
            if (index < steps.length) {
                const current = steps[index];
                if (loadingSubtext) loadingSubtext.textContent = current.text;
                if (progressBar) progressBar.style.width = current.progress;

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
                clearInterval(progressInterval);
            }
        }, 1100);
    }

    function showToast(msg) {
        toast.textContent = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3000);
    }

    function showElement(el) { if (el) el.classList.remove('hidden'); }
    function hideElement(el) { if (el) el.classList.add('hidden'); }

    // =========================================================================
    // SMART 4-COLUMN DAY-BY-DAY CARD & STRUCTURED SEGMENT RENDERERS
    // =========================================================================

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function parseDayTimeSlots(dayBodyText) {
        if (!dayBodyText) return '';
        const lines = dayBodyText.split('\n').map(l => l.trim()).filter(Boolean);
        let slotsHtml = '';
        let foundSpecificSlot = false;

        lines.forEach(line => {
            const cleanLine = line.replace(/^[\*\-\•\d+\.]\s*/, '').trim();
            if (!cleanLine) return;

            // Check for Morning, Afternoon, Evening, Stay/Highlights
            const slotMatch = cleanLine.match(/^(?:\*\*)?(Morning|Afternoon|Evening|Night|Stay|Highlights?(?:\s*(?:&|and)\s*Notes?)?|Notes?|Tips?|Accommodation)(?:\*\*)?[:\s\*\-]+(.*)$/i);
            if (slotMatch) {
                foundSpecificSlot = true;
                const rawSlotType = slotMatch[1].toLowerCase();
                let slotContent = slotMatch[2] ? slotMatch[2].trim() : '';

                // Clean out any residual '& Notes:', '& Note:', leading/trailing asterisks or colons
                slotContent = slotContent.replace(/^(&|and)?\s*notes?[:\s\*\-]*/i, '');
                slotContent = slotContent.replace(/^[\s\*\:\-]+/, '').replace(/[\s\*\-]+$/, '').trim();

                let iconClass = 'fa-solid fa-clock';
                let typeClass = 'morning';
                let label = slotMatch[1];

                if (rawSlotType.includes('morning')) {
                    iconClass = 'fa-solid fa-sun';
                    typeClass = 'morning';
                    label = 'Morning';
                } else if (rawSlotType.includes('afternoon')) {
                    iconClass = 'fa-solid fa-cloud-sun';
                    typeClass = 'afternoon';
                    label = 'Afternoon';
                } else if (rawSlotType.includes('evening') || rawSlotType.includes('night')) {
                    iconClass = 'fa-solid fa-moon';
                    typeClass = 'evening';
                    label = 'Evening';
                } else {
                    iconClass = 'fa-solid fa-star';
                    typeClass = 'highlight';
                    label = 'Highlights';
                }

                slotsHtml += `
                    <div class="time-slot ${typeClass}">
                        <span class="slot-tag"><i class="${iconClass}"></i> ${label}</span>
                        <div class="slot-desc">${typeof marked !== 'undefined' ? marked.parseInline(slotContent) : escapeHtml(slotContent)}</div>
                    </div>
                `;
            } else if (cleanLine.length > 0 && !cleanLine.startsWith('#')) {
                slotsHtml += `
                    <div class="time-slot">
                        <div class="slot-desc">${typeof marked !== 'undefined' ? marked.parseInline(cleanLine) : escapeHtml(cleanLine)}</div>
                    </div>
                `;
            }
        });

        if (!slotsHtml) {
            slotsHtml = `<div class="slot-desc">${typeof marked !== 'undefined' ? marked.parse(dayBodyText) : escapeHtml(dayBodyText)}</div>`;
        }

        return slotsHtml;
    }

    window.switchDaySubtab = function(containerId, index) {
        const wrapper = document.getElementById(`day-subtabs-${containerId}`);
        if (!wrapper) return;

        const cards = wrapper.querySelectorAll('.day-subtab-card');
        const panels = wrapper.querySelectorAll('.day-detail-panel');

        cards.forEach((card, idx) => {
            if (idx === index) card.classList.add('active');
            else card.classList.remove('active');
        });

        panels.forEach((panel, idx) => {
            if (idx === index) panel.classList.add('active');
            else panel.classList.remove('active');
        });
    };

    function renderInteractiveItinerary(markdownText, containerId = 'main') {
        if (!markdownText) return '<div class="para-highlight-card">No itinerary details generated yet.</div>';

        const text = String(markdownText);
        // Match Day headers: e.g. "### Day 1: ...", "**Day 1:** ...", "Day 1 - ..."
        const dayRegex = /(?:^|\n)(?:###?\s*|\*\*\s*|\b)Day\s*(\d+)[:\s–—\-]+([^\n*]+)(?:\*\*)?/gi;
        const matches = [...text.matchAll(dayRegex)];

        if (matches.length === 0) {
            return typeof marked !== 'undefined' ? marked.parse(text) : text;
        }

        const firstIndex = matches[0].index;
        const introText = text.substring(0, firstIndex).trim();

        const days = [];
        for (let i = 0; i < matches.length; i++) {
            const currentMatch = matches[i];
            const dayNum = currentMatch[1];
            const dayTitle = currentMatch[2].replace(/\*+/g, '').trim();
            const startPos = currentMatch.index + currentMatch[0].length;
            const endPos = (i + 1 < matches.length) ? matches[i + 1].index : text.length;
            const dayBodyRaw = text.substring(startPos, endPos).trim();

            let dayBody = dayBodyRaw;
            let outroText = '';
            if (i === matches.length - 1) {
                const outroSplit = dayBodyRaw.split(/(?:^|\n)(?=(?:###?\s*\d+\.|\b(?:Estimated Budget|Budget Analysis|Final Recommendations|Summary|Packing Tips|Conclusion)\b))/i);
                if (outroSplit.length > 1) {
                    dayBody = outroSplit[0].trim();
                    outroText = outroSplit.slice(1).join('\n').trim();
                }
            }

            // Extract a concise subtitle from stay or activity (e.g. "Sofia VIP • Grand Hotel")
            let subtitle = 'Highlights & Stays';
            const stayMatch = dayBody.match(/(?:Stay|Hotel|Resort|Accommodation)[:\s\*\-]+([^\n,.]+)/i);
            const morningMatch = dayBody.match(/(?:Morning)[:\s\*\-]+([^\n,.]+)/i);
            if (stayMatch) {
                subtitle = stayMatch[1].trim();
            } else if (morningMatch) {
                subtitle = morningMatch[1].trim();
            } else {
                const firstLine = dayBody.split('\n')[0].replace(/^[\*\-\•\d+\.]\s*/, '').trim();
                if (firstLine && firstLine.length > 3) {
                    subtitle = firstLine.substring(0, 28);
                }
            }

            days.push({
                num: dayNum,
                title: dayTitle,
                subtitle: subtitle,
                body: dayBody,
                outro: outroText
            });
        }

        // Generate Sub-tabs Row (Exact to User Reference Mockup)
        let subtabsHtml = `<div class="day-subtabs-wrapper" id="day-subtabs-${containerId}">`;
        subtabsHtml += `<div class="day-subtabs-row">`;

        days.forEach((d, idx) => {
            const activeClass = idx === 0 ? 'active' : '';
            subtabsHtml += `
                <div class="day-subtab-card ${activeClass}" onclick="switchDaySubtab('${containerId}', ${idx})" role="button" tabindex="0">
                    <div class="subtab-header">
                        <span class="subtab-day-badge">DAY ${d.num}</span>
                        <span class="subtab-day-label">Day ${d.num}</span>
                    </div>
                    <div class="subtab-title" title="${escapeHtml(d.title)}">${escapeHtml(d.title)}</div>
                    <div class="subtab-sub" title="${escapeHtml(d.subtitle)}">${escapeHtml(d.subtitle)}</div>
                    <div class="subtab-notch"></div>
                </div>
            `;
        });
        subtabsHtml += `</div>`; // end row

        // Generate Detailed Day Panels
        subtabsHtml += `<div class="day-details-container">`;
        days.forEach((d, idx) => {
            const activeClass = idx === 0 ? 'active' : '';
            const parsedSlots = parseDayTimeSlots(d.body);
            subtabsHtml += `
                <div class="day-detail-panel ${activeClass}" id="day-panel-${containerId}-${idx}">
                    <div class="day-panel-header">
                        <span class="day-panel-badge">DAY ${d.num}</span>
                        <h3 class="day-panel-title">${escapeHtml(d.title)}</h3>
                    </div>
                    <div class="day-panel-body">
                        ${parsedSlots}
                    </div>
                </div>
            `;
        });
        subtabsHtml += `</div></div>`; // end container & wrapper

        let resultHtml = '';
        if (introText) {
            resultHtml += `<div class="itinerary-overview-box">${typeof marked !== 'undefined' ? marked.parse(introText) : introText}</div>`;
        }
        resultHtml += subtabsHtml;

        const lastOutro = days[days.length - 1]?.outro;
        if (lastOutro) {
            resultHtml += `<div class="itinerary-outro-box">${typeof marked !== 'undefined' ? marked.parse(lastOutro) : lastOutro}</div>`;
        }

        return resultHtml;
    }

    function renderStructuredMasterPlan(markdownText) {
        if (!markdownText) return '';
        const text = String(markdownText);

        // Split by numbered sections: "1. Trip Summary", "2. Flight Information", etc.
        const sectionRegex = /(?:^|\n)(?:###?\s*|\*\*\s*|\b)(\d+)\.\s+([^\n*]+)(?:\*\*)?/g;
        const matches = [...text.matchAll(sectionRegex)];

        if (matches.length === 0) {
            return typeof marked !== 'undefined' ? marked.parse(text) : text;
        }

        let outputHtml = '';
        const topIntro = text.substring(0, matches[0].index).trim();
        if (topIntro) {
            outputHtml += `<div class="itinerary-overview-box">${typeof marked !== 'undefined' ? marked.parse(topIntro) : topIntro}</div>`;
        }

        for (let i = 0; i < matches.length; i++) {
            const current = matches[i];
            const secNum = current[1];
            const secTitle = current[2].replace(/\*+/g, '').trim();
            const startPos = current.index + current[0].length;
            const endPos = (i + 1 < matches.length) ? matches[i + 1].index : text.length;
            const secBody = text.substring(startPos, endPos).trim();

            let icon = 'fa-compass';
            if (secTitle.toLowerCase().includes('flight')) icon = 'fa-plane';
            else if (secTitle.toLowerCase().includes('hotel')) icon = 'fa-hotel';
            else if (secTitle.toLowerCase().includes('weather')) icon = 'fa-cloud-sun';
            else if (secTitle.toLowerCase().includes('itinerary')) icon = 'fa-calendar-days';
            else if (secTitle.toLowerCase().includes('budget')) icon = 'fa-wallet';
            else if (secTitle.toLowerCase().includes('recommendation')) icon = 'fa-award';

            let formattedBody = '';
            if (secTitle.toLowerCase().includes('itinerary')) {
                formattedBody = renderInteractiveItinerary(secBody, 'master');
            } else {
                formattedBody = `<div class="segment-body">${formatSegmentContent(secBody, secTitle.toLowerCase())}</div>`;
            }

            outputHtml += `
                <div class="plan-segment-card">
                    <div class="segment-header">
                        <span class="segment-num-badge"><i class="fa-solid ${icon}"></i></span>
                        <h3 class="segment-title">${secNum}. ${escapeHtml(secTitle)}</h3>
                    </div>
                    ${formattedBody}
                </div>
            `;
        }

        return outputHtml;
    }

    function formatSegmentContent(rawText, type) {
        if (!rawText) return '<p class="text-muted">No data available.</p>';
        let html = typeof marked !== 'undefined' ? marked.parse(rawText) : rawText;

        // Enhance flight information bullet items
        if (type.includes('flight')) {
            html = html.replace(/<li>(.*?)<\/li>/g, (m, p1) => {
                let badgeClass = 'detail-pill';
                if (p1.toLowerCase().includes('price') || p1.toLowerCase().includes('cost') || p1.toLowerCase().includes('airfare') || p1.includes('₹')) badgeClass += ' price';
                else if (p1.toLowerCase().includes('airline') || p1.toLowerCase().includes('flight')) badgeClass += ' airline';
                else if (p1.toLowerCase().includes('warning') || p1.toLowerCase().includes('season')) badgeClass += ' alert';
                return `<div class="para-highlight-card"><span class="${badgeClass}">${p1}</span></div>`;
            });
        }
        return html;
    }
});
