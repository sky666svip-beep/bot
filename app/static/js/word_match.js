document.addEventListener('DOMContentLoaded', () => {
    // === Variables ===
    const pairCountInput = document.getElementById('pairCount');
    const pairCountValue = document.getElementById('pairCountValue');
    const startBtn = document.getElementById('startBtn');
    const wordPanel = document.getElementById('wordPanel');
    const timerDisplay = document.getElementById('timerSeconds');
    const modal = document.getElementById('gameOverModal');
    const finalTimeSpan = document.getElementById('finalTime');
    const continueBtn = document.getElementById('continueBtn');
    const restartBtn = document.getElementById('restartBtn');

    let allWords = []; // Loaded from API
    let gameWords = []; // Currently active words (checking queue)
    let selectedBlock = null;
    let startTime = 0;
    let timerInterval = null;
    let matchedCount = 0;
    let totalPairs = 0;
    let isGameActive = false;
    let currentWordIndex = 0; 

    // Macaron Palette for JS usage (to generate accurate particle colors)
    const macaronColors = [
        { main: '#FFB7B2', light: '#FFD6D4', particle: '#FFC8C4', comp: '#B2FFF4' }, // Pink
        { main: '#B5EAD7', light: '#D9F5EB', particle: '#C9F0DF', comp: '#EAB5C8' }, // Mint
        { main: '#FFDAC1', light: '#FFF0E3', particle: '#FFE6D1', comp: '#C1E6FF' }, // Peach
        { main: '#E0BBE4', light: '#F1DEF2', particle: '#E8CCEB', comp: '#BBE4E0' }, // Purple
        { main: '#957DAD', light: '#B5A3C6', particle: '#A690BD', comp: '#C2AD95' }  // Deep Purple
    ];

    // === Event Listeners ===
    pairCountInput.addEventListener('input', () => {
        pairCountValue.textContent = pairCountInput.value;
    });

    startBtn.addEventListener('click', () => {
        startGame();
    });

    continueBtn.addEventListener('click', () => {
        modal.style.display = 'none';
        if (currentMode === "wordMatch") {
            continueGame();
        } else if (currentMode === "spelling") {
            startSpellingGame(); // Spelling just restarts round of 15
        } else if (currentMode === "quiz") {
            startQuizGame(); // Quiz just restarts round of 15
        }
    });

    restartBtn.addEventListener('click', () => {
        modal.style.display = 'none';
        if (currentMode === "wordMatch") {
            startGame();
        } else if (currentMode === "spelling") {
            startSpellingGame();
        } else if (currentMode === "quiz") {
            startQuizGame();
        }
    });

    // ==========================================
    // Shared Logic for New Modes
    // ==========================================
    const modeSelector = document.getElementById("modeSelector");
    const mainGameContainer = document.getElementById("mainGameContainer");
    const backToMenuBtn = document.getElementById("backToMenuBtn");
    
    const wordMatchSection = document.getElementById("wordMatchSection");
    const spellingSection = document.getElementById("spellingSection");
    const quizSection = document.getElementById("quizSection");

    const modalTitle = document.getElementById("modalTitle");
    const modalStats = document.getElementById("modalStats");
    const mistakeListContainer = document.getElementById("mistakeListContainer");
    const mistakeList = document.getElementById("mistakeList");

    let currentMode = "wordMatch";
    let mistakes = [];

    // Mode Selection
    document.querySelectorAll(".mode-card").forEach(card => {
        card.addEventListener("click", () => {
            currentMode = card.dataset.mode;
            modeSelector.style.display = "none";
            mainGameContainer.style.display = "block";
            
            // Hide all sections
            wordMatchSection.style.display = "none";
            spellingSection.style.display = "none";
            quizSection.style.display = "none";

            // Show selected section
            if (currentMode === "wordMatch") {
                wordMatchSection.style.display = "block";
                document.getElementById("gameTitle").innerText = "单词消消乐";
            } else if (currentMode === "spelling") {
                spellingSection.style.display = "block";
                document.getElementById("gameTitle").innerText = "拼写练习";
                startSpellingGame();
            } else if (currentMode === "quiz") {
                quizSection.style.display = "block";
                document.getElementById("gameTitle").innerText = "快速测验";
                startQuizGame();
            }
        });
    });

    backToMenuBtn.addEventListener("click", () => {
        resetGame(); // Stop timer etc from word match
        stopQuizTimer && stopQuizTimer(); // Stop quiz timer
        modeSelector.style.display = "flex";
        mainGameContainer.style.display = "none";
        modal.style.display = "none";
    });

    function showGameResult(title, statsHtml, modeMistakes) {
        modalTitle.innerText = title;
        modalStats.innerHTML = statsHtml;
        
        if (modeMistakes && modeMistakes.length > 0) {
            mistakeListContainer.style.display = "block";
            mistakeList.innerHTML = "";
            modeMistakes.forEach(m => {
                const li = document.createElement("li");
                li.innerHTML = `<span class="mistake-word">${m.word}</span> <span class="mistake-def">(${m.def})</span>`;
                mistakeList.appendChild(li);
            });
        } else {
            mistakeListContainer.style.display = "none";
        }

        modal.style.display = "flex";
    }

    // === Functions ===

    async function loadWords(count) {
        try {
            const response = await fetch(`/api/words?count=${count}`);
            const data = await response.json();
            if (data.success) {
                return data.data;
            } else {
                alert('加载单词失败: ' + data.message);
                return [];
            }
        } catch (error) {
            console.error('API Error:', error);
            alert('网络错误，无法加载单词');
            return [];
        }
    }

    async function startGame() {
        resetGame();
        
        startBtn.textContent = "加载中...";
        startBtn.disabled = true;

        const count = parseInt(pairCountInput.value);
        allWords = await loadWords(100); 

        startBtn.textContent = "重新开始（重置词汇）";
        startBtn.disabled = false;
        
        currentWordIndex = 0;
        initRound(count);
    }
    
    function continueGame() {
        const count = parseInt(pairCountInput.value);
        if (currentWordIndex >= allWords.length) {
            alert('所有单词已匹配完！重新加载新单词...');
            startGame();
            return;
        }
        initRound(count);
    }

    function initRound(count) {
        let sliceArgs = allWords.slice(currentWordIndex, currentWordIndex + count);
        
        if (sliceArgs.length === 0) {
            alert('没有更多单词了，重新开始！');
            startGame();
            return;
        }
        currentWordIndex += sliceArgs.length;
        
        gameWords = [];
        sliceArgs.forEach((item, index) => {
            // Assign random independent colors so pairs don't match by color
            const color1 = macaronColors[Math.floor(Math.random() * macaronColors.length)];
            const color2 = macaronColors[Math.floor(Math.random() * macaronColors.length)];

            gameWords.push({
                id: item.id,
                text: item.word,
                type: 'word',
                matchId: item.id,
                definition: item.definition,
                phonetic: item.phonetic,
                color: color1
            });
             gameWords.push({
                id: item.id,
                text: item.definition,
                type: 'def',
                matchId: item.id,
                word: item.word,
                color: color2
            });
        });

        gameWords.sort(() => Math.random() - 0.5);

        renderBoard(gameWords);
        resetTimer();
        startTimer();
    }

    function resetGame() {
        clearInterval(timerInterval);
        timerDisplay.textContent = "0.0";
        wordPanel.innerHTML = '';
        currentWordIndex = 0;
        allWords = [];
        isGameActive = false;
    }

    function resetTimer() {
        startTime = Date.now();
        clearInterval(timerInterval);
        timerDisplay.textContent = "0.0";
    }

    function startTimer() {
        isGameActive = true;
        startTime = Date.now();
        timerInterval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            timerDisplay.textContent = elapsed.toFixed(1);
        }, 100);
    }

    function stopTimer() {
        isGameActive = false;
        clearInterval(timerInterval);
    }

    function renderBoard(blocks) {
        wordPanel.innerHTML = '';
        matchedCount = 0;
        totalPairs = blocks.length / 2;

        blocks.forEach(block => {
            const div = document.createElement('div');
            div.className = 'word-block';
            div.innerText = block.text;
            div.dataset.id = block.matchId;
            div.dataset.type = block.type;
            
            // Apply gradient based on assigned color object
            div.style.background = `linear-gradient(135deg, ${block.color.main}, ${block.color.light})`;
            // Store color for explosion
            div.dataset.mainColor = block.color.main;
            div.dataset.particleColor = block.color.particle;
            div.dataset.compColor = block.color.comp;

            div.addEventListener('click', () => handleBlockClick(div, block));
            wordPanel.appendChild(div);
        });
    }

    function handleBlockClick(div, blockData) {
        if (!isGameActive) return;
        if (div.classList.contains('matched') || div.classList.contains('exploding')) return;
        
        if (div === selectedBlock) {
             div.classList.remove('selected');
             selectedBlock = null;
             return;
        }

        div.classList.add('selected');

        if (!selectedBlock) {
            selectedBlock = div;
        } else {
            const firstId = selectedBlock.dataset.id;
            const secondId = div.dataset.id;

            if (firstId === secondId) {
                handleMatch(selectedBlock, div, blockData);
            } else {
                handleMismatch(selectedBlock, div);
            }
            
            selectedBlock.classList.remove('selected');
            div.classList.remove('selected');
            selectedBlock = null;
        }
    }

    function handleMatch(el1, el2, blockData) {
        matchedCount++;
        
        // --- Stage 1: Trigger (Elastic Scale Up) ---
        // 0.1s scale up
        el1.classList.add('scaling');
        el2.classList.add('scaling');

        // Play Sound immediately
        let wordText = '';
        if (el1.dataset.type === 'word') wordText = el1.innerText;
        else if (el2.dataset.type === 'word') wordText = el2.innerText;
        if (wordText) speak(wordText);

        setTimeout(() => {
            // --- Stage 2 & 3: Explode & Scatter ---
            triggerExplosion(el1);
            triggerExplosion(el2);
            
            // Check Game Over after explosion starts
            checkGameOver();
        }, 100); 
    }

    function triggerExplosion(element) {
        const rect = element.getBoundingClientRect();
        const mainColor = element.dataset.mainColor;
        const particleColor = element.dataset.particleColor;
        const compColor = element.dataset.compColor; // Complementary for halo

        // Hide original element but keep layout space -> actually, creating an effect overlay ON TOP
        // element.style.visibility = 'hidden'; // Don't hide yet, or replace with empty placeholder?
        // Better: Make element transparent so it holds space, or replace content.
        element.style.opacity = '0';
        element.classList.add('exploding'); // Prevent clicks

        // Create Container for Effect (Absolute positioned over the element)
        // We append it to the body to ensure z-index top, but coordinates need match
        // OR append to wordPanel if relative. Body is safer for "no overflow" clipping if we monitor it, 
        // BUT requirement says "Do not overflow block boundary".
        // So we should append a container inside the element? No, element opacity is 0.
        // Let's create a temporary overlay div exactly at rect position.
        
        const overlay = document.createElement('div');
        overlay.style.position = 'fixed';
        overlay.style.left = rect.left + 'px';
        overlay.style.top = rect.top + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        overlay.style.zIndex = '9999';
        overlay.style.pointerEvents = 'none';
        overlay.style.overflow = 'hidden'; // STRICTLY CONTAINED within block area
        overlay.style.borderRadius = getComputedStyle(element).borderRadius; // Match rounded corners
        
        document.body.appendChild(overlay);

        // --- Halo Effect (1 frame flash) ---
        const halo = document.createElement('div');
        halo.style.position = 'absolute';
        halo.style.left = '0';
        halo.style.top = '0';
        halo.style.width = '100%';
        halo.style.height = '100%';
        halo.style.backgroundColor = compColor;
        halo.style.opacity = '0.4';
        halo.style.borderRadius = '50%'; // Soft halo
        halo.style.transform = 'scale(1.2)';
        halo.style.transition = 'opacity 0.05s';
        
        overlay.appendChild(halo);
        
        // 1 frame later hide halo
        requestAnimationFrame(() => {
            halo.style.opacity = '0';
        });

        // --- Particles ---
        const particleCount = 14 + Math.floor(Math.random() * 5); // 8-12
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        for (let i = 0; i < particleCount; i++) {
            const p = document.createElement('div');
            
            // Style
            const size = 5 + Math.random() * 10; // 2-5px
            p.style.width = size + 'px';
            p.style.height = size + 'px';
            p.style.backgroundColor = particleColor;
            p.style.borderRadius = '50%';
            p.style.position = 'absolute';
            p.style.left = (centerX - size/2) + 'px';
            p.style.top = (centerY - size/2) + 'px';
            p.style.opacity = '1';
            
            // Physics
            const angle = Math.random() * Math.PI * 2;
            const velocity = 30 + Math.random() * 50; // Max speed to stay within bounds approx.
            // 80px/s for 0.4s = 32px. Block width 120/2 = 60. Safe.
            
            const tx = Math.cos(angle) * 35; // Final distance x
            const ty = Math.sin(angle) * 35; // Final distance y
            const rotation = 144 + Math.random() * 216; // ~1 rot (360)

            // Animation
            // We use Web Animations API for precise control
            p.animate([
                { transform: `translate(0,0) rotate(0deg)`, opacity: 1 },
                { transform: `translate(${tx}px, ${ty}px) rotate(${rotation}deg)`, opacity: 0 }
            ], {
                duration: 1300,
                easing: 'cubic-bezier(0.25, 1, 0.5, 1)', // Deceleration curve
                fill: 'forwards'
            });

            overlay.appendChild(p);
        }

        // Cleanup
        setTimeout(() => {
            overlay.remove();
            element.style.visibility = 'hidden'; // Final state
        }, 1400); 
    }

    function handleMismatch(el1, el2) {
        el1.classList.add('mismatch');
        el2.classList.add('mismatch');

        setTimeout(() => {
            el1.classList.remove('mismatch');
            el2.classList.remove('mismatch');
        }, 500);
    }

    function checkGameOver() {
        if (matchedCount === totalPairs) {
            stopTimer();
            setTimeout(() => {
                 const statsHtml = `<p>本次耗时：<strong>${timerDisplay.textContent}</strong> 秒</p>`;
                 showGameResult("🎉 挑战成功！", statsHtml, null);
            }, 800);
        }
    }

    // TTS Function
    function speak(text) {
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'en-US'; 
            window.speechSynthesis.speak(utterance);
        }
    }

    // ==========================================
    // Spelling Practice Mode
    // ==========================================
    const spellingPrompt = document.getElementById("spellingPrompt");
    const spellingInput = document.getElementById("spellingInput");
    const checkSpellingBtn = document.getElementById("checkSpellingBtn");
    const spellingFeedback = document.getElementById("spellingFeedback");
    const spellingProgress = document.getElementById("spellingProgress");
    const spellingCounter = document.getElementById("spellingCounter");

    const SPELLING_ROUND_COUNT = 15;
    let spellingWords = [];
    let currentSpellingIndex = 0;
    let spellingCorrectCount = 0;

    async function startSpellingGame() {
        spellingPrompt.innerText = "加载中...";
        spellingInput.value = "";
        spellingInput.disabled = true;
        checkSpellingBtn.disabled = true;
        spellingFeedback.innerText = "";
        mistakes = [];
        spellingCorrectCount = 0;
        currentSpellingIndex = 0;

        spellingWords = await loadWords(SPELLING_ROUND_COUNT);
        
        if (spellingWords.length === 0) {
            alert("词库加载失败，请返回重试。");
            return;
        }

        spellingInput.disabled = false;
        checkSpellingBtn.disabled = false;
        loadNextSpellingWord();
    }

    function loadNextSpellingWord() {
        if (currentSpellingIndex >= spellingWords.length) {
            endSpellingGame();
            return;
        }

        const wordObj = spellingWords[currentSpellingIndex];
        spellingPrompt.innerText = wordObj.definition;
        spellingInput.value = "";
        spellingInput.className = "spelling-input"; // Reset classes
        spellingFeedback.innerText = "";
        spellingInput.focus();
        
        updateSpellingProgress();
    }

    function updateSpellingProgress() {
        spellingCounter.innerText = `${currentSpellingIndex + 1}/${spellingWords.length}`;
        const percent = ((currentSpellingIndex) / spellingWords.length) * 100;
        spellingProgress.style.width = `${percent}%`;
    }

    function checkSpelling() {
        const wordObj = spellingWords[currentSpellingIndex];
        const userAnswer = spellingInput.value.trim().toLowerCase();
        const correctAnswer = wordObj.word.toLowerCase();

        if (userAnswer === "") return;

        spellingInput.disabled = true;
        checkSpellingBtn.disabled = true;

        if (userAnswer === correctAnswer) {
            spellingInput.classList.add("correct");
            spellingFeedback.style.color = "#4CAF50";
            spellingFeedback.innerText = "正确！";
            spellingCorrectCount++;
            speak(wordObj.word);
        } else {
            spellingInput.classList.add("incorrect");
            spellingFeedback.style.color = "#F44336";
            spellingFeedback.innerHTML = `错误！正确答案是：<strong style="color:var(--color-primary)">${wordObj.word}</strong>`;
            mistakes.push({ word: wordObj.word, def: wordObj.definition });
            speak(wordObj.word);
        }

        setTimeout(() => {
            currentSpellingIndex++;
            spellingInput.disabled = false;
            checkSpellingBtn.disabled = false;
            loadNextSpellingWord();
        }, 1500);
    }

    spellingInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !spellingInput.disabled) {
            checkSpelling();
        }
    });

    checkSpellingBtn.addEventListener("click", () => {
        if (!checkSpellingBtn.disabled) checkSpelling();
    });

    function endSpellingGame() {
        spellingProgress.style.width = "100%";
        spellingCounter.innerText = `${spellingWords.length}/${spellingWords.length}`;
        
        const accuracy = Math.round((spellingCorrectCount / spellingWords.length) * 100);
        const statsHtml = `
            <p>答对：<strong>${spellingCorrectCount}</strong> / ${spellingWords.length}</p>
            <p>准确率：<strong>${accuracy}%</strong></p>
        `;
        
        showGameResult("🎉 拼写练习完成！", statsHtml, mistakes);
    }

    // ==========================================
    // Quick Quiz Mode
    // ==========================================
    const quizPrompt = document.getElementById("quizPrompt");
    const quizOptionsContainer = document.getElementById("quizOptions");
    const quizFeedback = document.getElementById("quizFeedback");
    const quizProgress = document.getElementById("quizProgress");
    const quizCounter = document.getElementById("quizCounter");
    const quizTimerDisplay = document.getElementById("quizTimerSeconds");

    const QUIZ_ROUND_COUNT = 15;
    let quizBank = []; // Larger pool for options
    let quizQuestions = []; // Selected questions
    let currentQuizIndex = 0;
    let quizCorrectCount = 0;
    let quizTimerInterval = null;
    let quizStartTime = 0;

    async function startQuizGame() {
        quizPrompt.innerText = "加载中...";
        quizOptionsContainer.innerHTML = "";
        quizFeedback.innerText = "";
        mistakes = [];
        quizCorrectCount = 0;
        currentQuizIndex = 0;

        // Load a larger bank to get enough incorrect options
        quizBank = await loadWords(60);
        
        if (quizBank.length < 4) {
             alert("词库加载失败或单词太少，请返回重试。");
             return;
        }

        // Pick round count questions
        quizQuestions = quizBank.slice(0, QUIZ_ROUND_COUNT);
        
        startQuizTimer();
        loadNextQuizQuestion();
    }

    function startQuizTimer() {
        quizStartTime = Date.now();
        clearInterval(quizTimerInterval);
        quizTimerDisplay.textContent = "0.0";
        quizTimerInterval = setInterval(() => {
            const elapsed = (Date.now() - quizStartTime) / 1000;
            quizTimerDisplay.textContent = elapsed.toFixed(1);
        }, 100);
    }

    function stopQuizTimer() {
        clearInterval(quizTimerInterval);
    }

    function loadNextQuizQuestion() {
        if (currentQuizIndex >= quizQuestions.length) {
            endQuizGame();
            return;
        }

        const questionWord = quizQuestions[currentQuizIndex];
        const isEngToZho = Math.random() > 0.5; // 50% chance

        // Generate options
        let options = [];
        let correctOptionText = isEngToZho ? questionWord.definition : questionWord.word;
        
        options.push(correctOptionText);

        // Get 3 random wrong options
        let attempts = 0;
        while (options.length < 4 && attempts < 100) {
            attempts++;
            const randomWord = quizBank[Math.floor(Math.random() * quizBank.length)];
            if (randomWord.id === questionWord.id) continue;
            
            const wrongText = isEngToZho ? randomWord.definition : randomWord.word;
            if (!options.includes(wrongText)) {
                options.push(wrongText);
            }
        }

        // Shuffle options
        options.sort(() => Math.random() - 0.5);

        // Render Question
        quizPrompt.innerText = isEngToZho ? questionWord.word : questionWord.definition;
        
        // Always speak english part if we are displaying it, or wait for user to click?
        if (isEngToZho) {
            speak(questionWord.word);
        }

        quizOptionsContainer.innerHTML = "";
        quizFeedback.innerText = "";
        
        options.forEach(optText => {
            const btn = document.createElement("div");
            btn.className = "quiz-option";
            btn.innerText = optText;
            btn.onclick = () => handleQuizClick(btn, optText, correctOptionText, questionWord);
            quizOptionsContainer.appendChild(btn);
        });

        updateQuizProgress();
    }

    function updateQuizProgress() {
        quizCounter.innerText = `${currentQuizIndex + 1}/${quizQuestions.length}`;
        const percent = ((currentQuizIndex) / quizQuestions.length) * 100;
        quizProgress.style.width = `${percent}%`;
    }

    function handleQuizClick(clickedBtn, selectedText, correctText, questionWord) {
        // Disable all buttons to prevent double clicking
        const allBtns = quizOptionsContainer.querySelectorAll(".quiz-option");
        allBtns.forEach(btn => btn.style.pointerEvents = "none");

        if (selectedText === correctText) {
            clickedBtn.classList.add("correct");
            quizFeedback.style.color = "#4CAF50";
            quizFeedback.innerText = "正确！";
            quizCorrectCount++;
        } else {
            clickedBtn.classList.add("incorrect");
            // Find and highlight correct answer
            allBtns.forEach(btn => {
                if (btn.innerText === correctText) {
                    btn.classList.add("correct");
                }
            });
            quizFeedback.style.color = "#F44336";
            quizFeedback.innerText = "错误！";
            mistakes.push({ word: questionWord.word, def: questionWord.definition });
        }
        
        speak(questionWord.word);

        setTimeout(() => {
            currentQuizIndex++;
            loadNextQuizQuestion();
        }, 1200);
    }

    function endQuizGame() {
        stopQuizTimer();
        quizProgress.style.width = "100%";
        quizCounter.innerText = `${quizQuestions.length}/${quizQuestions.length}`;
        
        const accuracy = Math.round((quizCorrectCount / quizQuestions.length) * 100);
        const statsHtml = `
            <p>本次耗时：<strong>${quizTimerDisplay.textContent}</strong> 秒</p>
            <p>答对：<strong>${quizCorrectCount}</strong> / ${quizQuestions.length}</p>
            <p>准确率：<strong>${accuracy}%</strong></p>
        `;
        
        showGameResult("🎉 快速测验完成！", statsHtml, mistakes);
    }

    // ==========================================
    // Word Search Dictionary (Fuzzy Search)
    // ==========================================
    const searchInput = document.getElementById("wordSearchInput");
    const searchResults = document.getElementById("wordSearchResults");
    let searchTimeout = null;

    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            const val = e.target.value.trim();
            clearTimeout(searchTimeout);
            
            if (!val) {
                searchResults.style.display = 'none';
                return;
            }
            
            // Show loading state implicitly by waiting
            searchTimeout = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/words/search?keyword=${encodeURIComponent(val)}`);
                    const data = await res.json();
                    
                    if (data.success && data.data.length > 0) {
                        renderSearchResults(data.data);
                    } else {
                        searchResults.innerHTML = '<div style="padding: 15px; text-align: center; color: #888; font-weight: bold;">暂无匹配结果</div>';
                        searchResults.style.display = 'flex';
                    }
                } catch (err) {
                    console.error("Search API error", err);
                }
            }, 300); // 300ms debounce
        });
        
        // Hide when clicking outside
        document.addEventListener("click", (e) => {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.style.display = 'none';
            }
        });
        
        // Show again when focusing on input if it has results
        searchInput.addEventListener("focus", () => {
            if (searchInput.value.trim() && searchResults.innerHTML !== "") {
                searchResults.style.display = 'flex';
            }
        });
    }

    function renderSearchResults(results) {
        searchResults.innerHTML = "";
        results.forEach(item => {
            const div = document.createElement("div");
            div.className = "search-result-item";
            
            div.innerHTML = `
                <div class="sr-word">
                    <span>${item.word}</span>
                    <span class="sr-phonetic">${item.phonetic || ''}</span>
                    <span style="font-size:0.8rem; background:var(--color-primary); color:white; padding:2px 8px; border-radius:12px; margin-left:auto; box-shadow:0 2px 4px rgba(0,0,0,0.1);">🔊 朗读</span>
                </div>
                <div class="sr-def">${item.definition || '暂无释义'}</div>
            `;
            
            div.addEventListener("click", () => {
                speak(item.word);
                // Optional visual feedback on click
                div.style.background = 'rgba(255, 183, 178, 0.3)';
                setTimeout(() => div.style.background = '', 200);
            });
            
            searchResults.appendChild(div);
        });
        searchResults.style.display = 'flex';
    }
});
