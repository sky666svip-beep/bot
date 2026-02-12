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
        continueGame();
    });

    restartBtn.addEventListener('click', () => {
        modal.style.display = 'none';
        startGame();
    });

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
                 finalTimeSpan.textContent = timerDisplay.textContent;
                 modal.style.display = 'flex';
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
});
