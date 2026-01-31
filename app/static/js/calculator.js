// 全局状态
let currentExpression = "";
let displayValue = "0";
let isRadians = false; // 默认角度制
let isResultDisplayed = false;

// DOM 元素
const displayEl = document.getElementById('calc-display');
const historyEl = document.getElementById('calc-history');
const degRadBtn = document.getElementById('deg-rad-btn');

// --- 导航切换逻辑 ---
const navButtons = document.querySelectorAll('.nav-btn');
const panels = document.querySelectorAll('.panel');

navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        // 移除激活状态
        navButtons.forEach(b => b.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));

        // 激活当前
        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active');
    });
});

// --- 角度/弧度 切换 ---
if (degRadBtn) {
    degRadBtn.addEventListener('click', () => {
        isRadians = !isRadians;
        degRadBtn.innerText = isRadians ? 'RAD' : 'DEG';
        degRadBtn.style.color = isRadians ? '#d900ff' : '#00bcd4';
    });
}

// --- 计算器核心逻辑 ---

function updateDisplay() {
    if(!displayEl) return;
    displayEl.innerText = displayValue;
    historyEl.innerText = currentExpression.replace(/\*/g, '×').replace(/\//g, '÷');
}

// 输入数字
function inputNumber(num) {
    if (isResultDisplayed) {
        displayValue = num.toString();
        currentExpression = num.toString();
        isResultDisplayed = false;
    } else {
        if (displayValue === "0" && num !== '.') {
            displayValue = num.toString();
        } else {
            if (num === '.' && displayValue.includes('.') && !/[\+\-\*\/]/.test(displayValue.slice(-1))) {
                return;
            }
            displayValue += num;
        }
        currentExpression += num;
    }
    updateDisplay();
}

// 输入基础运算符
function inputOperator(op) {
    if (isResultDisplayed) {
        isResultDisplayed = false;
    }
    const lastChar = currentExpression.slice(-1);
    if (['+', '-', '*', '/', '%', '^'].includes(lastChar)) {
        currentExpression = currentExpression.slice(0, -1) + op;
    } else {
        currentExpression += op;
    }
    displayValue = "0";
    updateDisplay();
}

// 输入常量
function insertConstant(constName) {
    let val = '';
    let disp = '';
    if (constName === 'PI') {
        val = Math.PI.toFixed(8);
        disp = 'π';
    } else if (constName === 'E') {
        val = Math.E.toFixed(8);
        disp = 'e';
    }
    if (isResultDisplayed) {
        currentExpression = val;
        isResultDisplayed = false;
    } else {
        currentExpression += val;
    }
    displayValue = disp;
    updateDisplay();
}

// 输入函数
function inputFunc(func) {
    if (isResultDisplayed) {
        currentExpression = "";
        isResultDisplayed = false;
    }
    if (func === 'fact') {
        currentExpression += '!';
        displayValue = "n!";
    } else if (func === 'recip') {
        currentExpression += '^(-1)';
        displayValue = "1/x";
    } else {
        currentExpression += func + '(';
        displayValue = func + "(";
    }
    updateDisplay();
}

// 清除与退格
function clearDisplay() {
    currentExpression = "";
    displayValue = "0";
    isResultDisplayed = false;
    updateDisplay();
}

function backspace() {
    if (isResultDisplayed) {
        clearDisplay();
        return;
    }
    currentExpression = currentExpression.toString().slice(0, -1);
    displayValue = displayValue.toString().slice(0, -1);
    if (displayValue === "") displayValue = "0";
    updateDisplay();
}

// 执行计算 (简化版 eval)
function calculate() {
    let evalString = currentExpression;
    try {
        evalString = evalString.replace(/(\d+)!/g, "factorial($1)");
        evalString = evalString.replace(/\^/g, "**");

        const toRad = (val) => isRadians ? val : val * (Math.PI / 180);

        evalString = evalString
            .replace(/sin\(/g, `Math.sin(${isRadians ? '' : 'Math.PI/180*'} `)
            .replace(/cos\(/g, `Math.cos(${isRadians ? '' : 'Math.PI/180*'} `)
            .replace(/tan\(/g, `Math.tan(${isRadians ? '' : 'Math.PI/180*'} `)
            .replace(/asin\(/g, `${isRadians ? '' : '180/Math.PI*'}Math.asin(`)
            .replace(/acos\(/g, `${isRadians ? '' : '180/Math.PI*'}Math.acos(`)
            .replace(/atan\(/g, `${isRadians ? '' : '180/Math.PI*'}Math.atan(`)
            .replace(/log\(/g, "Math.log10(")
            .replace(/ln\(/g, "Math.log(")
            .replace(/sqrt\(/g, "Math.sqrt(")
            .replace(/cbrt\(/g, "Math.cbrt(");

        const factorial = (n) => {
            if(n<0) return NaN;
            if(n==0||n==1) return 1;
            let r=1; for(let i=2;i<=n;i++) r*=i;
            return r;
        };

        let result = eval(evalString);

        if (!isFinite(result)) {
            displayValue = "Error";
        } else {
            result = parseFloat(result.toFixed(10));
            displayValue = result.toString();
            currentExpression = result.toString();
        }
        isResultDisplayed = true;
    } catch (e) {
        displayValue = "Syntax Error";
        currentExpression = "";
        isResultDisplayed = true;
    }
    updateDisplay();
}

// --- 单位换算逻辑 ---

const unitData = {
    length: {
        units: { 'm': '米 (m)', 'km': '千米 (km)', 'cm': '厘米 (cm)', 'mm': '毫米 (mm)', 'in': '英寸 (in)', 'ft': '英尺 (ft)' },
        rates: { 'm': 1, 'km': 1000, 'cm': 0.01, 'mm': 0.001, 'in': 0.0254, 'ft': 0.3048 }
    },
    area: {
        units: {
            'm2': '平方米 (m²)', 'km2': '平方千米 (km²)', 'ha': '公顷 (ha)',
            'dm2': '平方分米 (dm²)', 'cm2': '平方厘米 (cm²)', 'mm2': '平方毫米 (mm²)'
        },
        rates: {
            'm2': 1, 'km2': 1000000, 'ha': 10000,
            'dm2': 0.01, 'cm2': 0.0001, 'mm2': 0.000001
        }
    },
    volume: {
        units: {
            'm3': '立方米 (m³)', 'dm3': '立方分米 (dm³)', 'cm3': '立方厘米 (cm³)', 'mm3': '立方毫米 (mm³)', 'L': '升 (L)'
        },
        rates: {
            'm3': 1, 'dm3': 0.001, 'cm3': 0.000001, 'mm3': 1e-9, 'L': 0.001
        }
    },
    mass: {
        units: { 'kg': '千克 (kg)', 'g': '克 (g)', 't': '吨 (t)', 'lb': '磅 (lb)', 'oz': '盎司 (oz)' },
        rates: { 'kg': 1, 'g': 0.001, 't': 1000, 'lb': 0.453592, 'oz': 0.0283495 }
    },
    time: {
        units: { 's': '秒', 'min': '分', 'h': '时', 'd': '天', 'ms': '毫秒' },
        rates: { 's': 1, 'min': 60, 'h': 3600, 'd': 86400, 'ms': 0.001 }
    },
    temp: {
        units: { 'C': '摄氏度 ℃', 'F': '华氏度 ℉', 'K': '开尔文 K' }
    }
};

let currentUnitType = 'length';

function initUnitSelects() {
    const fromSelect = document.getElementById('unit-from');
    const toSelect = document.getElementById('unit-to');

    fromSelect.innerHTML = '';
    toSelect.innerHTML = '';

    if(!unitData[currentUnitType]) return;

    const units = unitData[currentUnitType].units;
    for (const key in units) {
        fromSelect.add(new Option(units[key], key));
        toSelect.add(new Option(units[key], key));
    }

    toSelect.selectedIndex = 1; // 默认选中第二个
    convert();
}

function switchUnitType(type) {
    currentUnitType = type;
    document.querySelectorAll('.unit-tab').forEach(btn => {
        btn.classList.remove('active');
        // 简单的文本匹配，确保按钮文字包含关键字即可
        if(btn.onclick.toString().includes(type)) {
            btn.classList.add('active');
        }
    });
    initUnitSelects();
}

function convert() {
    const inputEl = document.getElementById('unit-input');
    if(!inputEl) return;

    const val = parseFloat(inputEl.value);
    const from = document.getElementById('unit-from').value;
    const to = document.getElementById('unit-to').value;
    const resultEl = document.getElementById('unit-result');
    const symbolEl = document.getElementById('unit-symbol');

    if (isNaN(val)) {
        resultEl.innerText = "--";
        return;
    }

    let result;

    if (currentUnitType === 'temp') {
        let valInC;
        if (from === 'C') valInC = val;
        else if (from === 'F') valInC = (val - 32) * 5/9;
        else if (from === 'K') valInC = val - 273.15;

        if (to === 'C') result = valInC;
        else if (to === 'F') result = (valInC * 9/5) + 32;
        else if (to === 'K') result = valInC + 273.15;
    } else {
        const rates = unitData[currentUnitType].rates;
        const baseVal = val * rates[from];
        result = baseVal / rates[to];
    }

    let formatted = parseFloat(result.toFixed(6));
    resultEl.innerText = formatted;

    // 获取单位符号 (括号里的内容)
    const unitLabel = unitData[currentUnitType].units[to];
    const match = unitLabel.match(/\((.*?)\)/);
    symbolEl.innerText = match ? match[1] : '';
}

window.onload = () => {
    initUnitSelects();
};