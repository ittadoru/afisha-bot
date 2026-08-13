import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "/Users/skh/Documents/VSFiles/AfishaBot/Машинное_обучение_15_слайдов.pptx";
const PREVIEW = "/Users/skh/Documents/VSFiles/AfishaBot/.codex_tmp/ml_deck_20260812/final-preview";

const C = {
  bg: "#F4F6FA",
  paper: "#FFFFFF",
  ink: "#172033",
  indigo: "#26365F",
  blue: "#6176B5",
  pale: "#E7EBF5",
  pale2: "#D7DEEF",
  orange: "#F59E0B",
  orange2: "#FFB84D",
  muted: "#667085",
  green: "#2F7D6D",
  red: "#C95A5A",
};

const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function addShape(slide, geometry, x, y, w, h, fill = "none", line = "none", radius = undefined, name = undefined) {
  const shape = slide.shapes.add({
    geometry,
    name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: line === "none" ? { style: "solid", fill: "none", width: 0 } : line,
    ...(radius ? { borderRadius: radius } : {}),
  });
  return shape;
}

function addText(slide, text, x, y, w, h, opts = {}) {
  const shape = addShape(slide, opts.geometry || "textbox", x, y, w, h, opts.fill || "none", opts.line || "none", opts.radius, opts.name);
  shape.text = text;
  shape.text.style = {
    typeface: opts.typeface || "Arial",
    fontSize: opts.size || 24,
    bold: opts.bold || false,
    italic: opts.italic || false,
    color: opts.color || C.ink,
    alignment: opts.align || "left",
    verticalAlignment: opts.valign || "top",
    autoFit: "shrinkText",
    wrap: "square",
    lineSpacing: opts.lineSpacing || 1.0,
    insets: opts.insets || { left: 0, right: 0, top: 0, bottom: 0 },
  };
  return shape;
}

function addHeader(slide, number, title, dark = false) {
  const fg = dark ? "#FFFFFF" : C.ink;
  addText(slide, number, 64, 42, 58, 28, { size: 16, bold: true, color: dark ? C.orange2 : C.orange, valign: "middle" });
  addText(slide, title, 64, 78, 1120, 64, { size: 46, bold: true, color: fg, valign: "middle" });
  addShape(slide, "rect", 64, 150, 72, 5, C.orange, "none", 2);
}

function addFooter(slide, n, dark = false) {
  addText(slide, String(n).padStart(2, "0"), 1170, 671, 48, 20, { size: 14, bold: true, color: dark ? "#AAB4D4" : "#9AA3B5", align: "right" });
}

function addNotes(slide, text, source) {
  slide.speakerNotes.textFrame.setText(`${text ? text + "\n\n" : ""}[Sources]\n- ${source}\n[/Sources]`);
}

function pill(slide, text, x, y, w, fill, color = "#FFFFFF", size = 20) {
  return addText(slide, text, x, y, w, 46, { size, bold: true, color, fill, geometry: "roundRect", radius: 23, align: "center", valign: "middle", insets: { left: 12, right: 12, top: 4, bottom: 4 } });
}

function arrow(slide, x, y, w = 64, h = 26, fill = C.orange) {
  return addShape(slide, "rightArrow", x, y, w, h, fill, "none", undefined);
}

function circleLabel(slide, text, x, y, d, fill, color = "#FFFFFF", size = 24) {
  const circle = addShape(slide, "ellipse", x, y, d, d, fill, "none");
  addText(slide, text, x + 8, y + 8, d - 16, d - 16, { size, bold: true, color, align: "center", valign: "middle", insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  return circle;
}

// 1 — Title: all original text retained verbatim.
{
  const s = deck.slides.add();
  s.background.fill = C.indigo;
  addShape(s, "ellipse", 850, 80, 420, 420, "#324574", "none");
  addShape(s, "ellipse", 940, 155, 280, 280, C.orange, "none");
  addText(s, "ML", 980, 215, 200, 125, { size: 74, bold: true, color: C.indigo, align: "center", valign: "middle" });
  addShape(s, "ellipse", 1125, 92, 18, 18, C.orange2, "none");
  addShape(s, "ellipse", 918, 465, 14, 14, "#FFFFFF", "none");
  addShape(s, "ellipse", 1220, 520, 10, 10, C.orange2, "none");
  addText(s, "Машинное обучение:\nпонятие, виды", 66, 92, 760, 190, { size: 62, bold: true, color: "#FFFFFF", lineSpacing: 0.93 });
  addText(s, "Machine learning", 68, 298, 420, 42, { size: 27, color: C.orange2, italic: true });
  addShape(s, "rect", 68, 370, 650, 2, "#7180AA", "none");
  addText(s, "Цель: изучить понятие и основные виды машинного обучения, различия между обучением с учителем и без учителя, задачи машинного обучения и принципы отбора данных.", 68, 396, 700, 112, { size: 22, color: "#DDE3F2", lineSpacing: 1.12 });
  pill(s, "Камалудинов Х. М.", 68, 585, 250, "#FFFFFF", C.indigo, 18);
  addFooter(s, 1, true);
  addNotes(s, "Титульный слайд. Текст сохранён без изменений.", "Исходная презентация пользователя, слайд 1.");
}

// 2 — Activation questions.
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  addHeader(s, "01", "Актуализация знаний");
  const items = [
    ["Что называют искусственным интеллектом?", 190, C.indigo],
    ["Где используются системы, которые обучаются на данных?", 275, C.blue],
    ["Как компьютер может научиться распознавать объекты или прогнозировать результат?", 382, C.indigo],
    ["Какие данные могут использоваться для обучения модели?", 510, C.blue],
  ];
  items.forEach(([t, y, fill], i) => {
    circleLabel(s, String(i + 1), 70, y, 44, i === 2 ? C.orange : fill, "#FFFFFF", 20);
    addText(s, t, 140, y - 2, i === 2 ? 940 : 870, i === 2 ? 86 : 58, { size: i === 2 ? 26 : 25, bold: i === 2, color: C.ink, valign: "middle", lineSpacing: 1.05 });
    if (i < 3) addShape(s, "rect", 140, y + (i === 2 ? 95 : 68), 820, 1, C.pale2, "none");
  });
  addShape(s, "ellipse", 1045, 210, 150, 150, C.pale, "none");
  addShape(s, "ellipse", 1082, 247, 76, 76, C.orange, "none");
  addText(s, "?", 1095, 253, 50, 60, { size: 47, bold: true, color: "#FFFFFF", align: "center", valign: "middle" });
  addText(s, "27 JULY 2026", 1030, 410, 180, 24, { size: 14, bold: true, color: C.muted, align: "center" });
  addText(s, "27 JULY 2026", 1030, 446, 180, 24, { size: 14, color: C.orange, align: "center" });
  addFooter(s, 2);
  addNotes(s, "Вопросы выводятся последовательно для короткого обсуждения.", "Исходная презентация пользователя, слайд 2.");
}

// 3 — Terms as a semantic constellation.
{
  const s = deck.slides.add();
  s.background.fill = C.indigo;
  addHeader(s, "02", "Ключевые слова", true);
  addShape(s, "ellipse", 440, 235, 400, 250, "#314575", "none");
  addText(s, "машинное обучение", 490, 310, 300, 80, { size: 32, bold: true, color: "#FFFFFF", align: "center", valign: "middle" });
  pill(s, "данные", 86, 250, 180, C.orange, C.indigo, 22);
  pill(s, "модель машинного обучения", 82, 440, 300, "#FFFFFF", C.indigo, 19);
  pill(s, "обучение с учителем", 875, 220, 290, C.blue, "#FFFFFF", 19);
  pill(s, "обучение без учителя", 895, 332, 290, "#FFFFFF", C.indigo, 19);
  pill(s, "регрессия", 250, 580, 190, "#FFFFFF", C.indigo, 20);
  pill(s, "классификация", 530, 570, 220, C.orange, C.indigo, 20);
  pill(s, "кластеризация", 855, 550, 220, C.blue, "#FFFFFF", 20);
  addText(s, "27 JULY 2026", 1045, 64, 170, 20, { size: 13, color: "#AFB8D3", align: "right" });
  addText(s, "27 JULY 2026", 1045, 92, 170, 20, { size: 13, color: C.orange2, align: "right" });
  addFooter(s, 3, true);
  addNotes(s, "Термины расположены вокруг центрального понятия.", "Исходная презентация пользователя, слайд 3.");
}

// 4 — Case setup.
{
  const s = deck.slides.add();
  s.background.fill = C.paper;
  addHeader(s, "03", "Ситуационная задача");
  addText(s, "Имеются данные об успеваемости студентов. Нужно спрогнозировать итоговый балл, определить вероятность сдачи экзамена и объединить студентов в группы по схожим результатам.", 72, 210, 630, 250, { size: 30, bold: true, color: C.indigo, lineSpacing: 1.15 });
  addShape(s, "rect", 760, 195, 6, 370, C.orange, "none", 3);
  const qs = ["Какая задача относится к регрессии?", "Какая к классификации?", "Какая к кластеризации?"];
  qs.forEach((q, i) => {
    circleLabel(s, String(i + 1), 810, 205 + i * 120, 48, i === 0 ? C.orange : C.blue, "#FFFFFF", 21);
    addText(s, q, 885, 202 + i * 120, 300, 74, { size: 24, bold: true, color: C.ink, valign: "middle" });
  });
  addText(s, "Сформулируйте гипотезу до разбора видов обучения", 72, 575, 630, 44, { size: 20, color: C.muted });
  addFooter(s, 4);
  addNotes(s, "Сначала аудитория распределяет три задачи по типам.", "Исходная презентация пользователя, слайд 4.");
}

// 5 — Definition.
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  addHeader(s, "04", "Машинное обучение учится на данных");
  addText(s, "Машинное обучение — это направление искусственного интеллекта, при котором компьютерная модель обучается на данных и использует полученные закономерности для решения задач.", 72, 205, 530, 215, { size: 27, color: C.ink, lineSpacing: 1.15 });
  addText(s, "Главная идея", 72, 470, 210, 32, { size: 19, bold: true, color: C.orange });
  addText(s, "Не прописывать каждое правило вручную, а обучить модель находить закономерности.", 72, 510, 540, 105, { size: 27, bold: true, color: C.indigo, lineSpacing: 1.08 });
  arrow(s, 765, 330, 70, 30, C.orange);
  arrow(s, 1010, 330, 70, 30, C.orange);
  circleLabel(s, "Данные", 650, 265, 130, C.blue, "#FFFFFF", 23);
  circleLabel(s, "Модель", 865, 265, 130, C.indigo, "#FFFFFF", 23);
  circleLabel(s, "Решение", 1100, 265, 130, C.orange, C.indigo, 23);
  addText(s, "Machine\nLearning", 840, 455, 290, 120, { size: 42, bold: true, color: C.pale2, align: "center", valign: "middle" });
  addFooter(s, 5);
  addNotes(s, "Определение сокращено визуально, смысл исходного текста сохранён.", "Исходная презентация пользователя, слайд 5.");
}

// 6 — Applications.
{
  const s = deck.slides.add();
  s.background.fill = C.paper;
  addHeader(s, "05", "Где машинное обучение приносит пользу");
  const apps = [
    ["01", "Распознавание изображений", "объекты • лица • снимки"],
    ["02", "Прогнозирование результатов", "спрос • цена • риск"],
    ["03", "Обнаружение спама", "почта • сообщения • звонки"],
    ["04", "Анализ больших данных", "поиск связей и аномалий"],
  ];
  apps.forEach((a, i) => {
    const x = i % 2 === 0 ? 72 : 660;
    const y = i < 2 ? 205 : 430;
    addShape(s, "rect", x, y + 66, 500, 2, C.pale2, "none");
    circleLabel(s, a[0], x, y, 54, i === 2 ? C.orange : C.indigo, "#FFFFFF", 18);
    addText(s, a[1], x + 82, y, 430, 42, { size: 26, bold: true, color: C.ink });
    addText(s, a[2], x + 82, y + 45, 410, 30, { size: 19, color: C.muted });
  });
  addFooter(s, 6);
  addNotes(s, "Четыре области применения сведены к коротким примерам.", "Исходная презентация пользователя, слайд 6.");
}

// 7 — Three types.
{
  const s = deck.slides.add();
  s.background.fill = C.indigo;
  addHeader(s, "06", "Три основных вида машинного обучения", true);
  const types = [
    ["1", "С учителем", "Данные размечены:\nесть правильные ответы", C.orange],
    ["2", "Без учителя", "Данные не размечены:\nструктуру ищет модель", C.blue],
    ["3", "С подкреплением", "Опыт: действие →\nнаграда или штраф", "#FFFFFF"],
  ];
  types.forEach((t, i) => {
    const x = 72 + i * 400;
    addText(s, t[0], x, 215, 80, 100, { size: 74, bold: true, color: t[3] === "#FFFFFF" ? C.orange2 : t[3] });
    addText(s, t[1], x, 325, 335, 60, { size: 30, bold: true, color: "#FFFFFF" });
    addShape(s, "rect", x, 402, 280, 3, t[3] === "#FFFFFF" ? C.orange2 : t[3], "none");
    addText(s, t[2], x, 430, 320, 115, { size: 23, color: "#DCE2F1", lineSpacing: 1.15 });
  });
  addText(s, "Правильные ответы", 72, 604, 260, 28, { size: 17, bold: true, color: C.orange2 });
  addText(s, "Скрытая структура", 472, 604, 260, 28, { size: 17, bold: true, color: "#AFC0F4" });
  addText(s, "Обратная связь", 872, 604, 260, 28, { size: 17, bold: true, color: "#FFFFFF" });
  addFooter(s, 7, true);
  addNotes(s, "Три вида различаются источником обучающего сигнала.", "Текст пользователя для слайда 7.");
}

// 8 — Supervised learning.
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  addHeader(s, "07", "С учителем: примеры уже имеют ответы");
  addText(s, "Модель тренируется на парах «входные данные + верный ответ».", 72, 184, 720, 45, { size: 25, color: C.muted });
  arrow(s, 310, 295, 65, 30, C.orange);
  arrow(s, 585, 295, 65, 30, C.orange);
  arrow(s, 850, 295, 65, 30, C.orange);
  const a = circleLabel(s, "Данные", 125, 245, 130, C.blue, "#FFFFFF", 22);
  const b = circleLabel(s, "+ ответ", 400, 245, 130, C.orange, C.indigo, 22);
  const c = circleLabel(s, "Модель", 675, 245, 130, C.indigo, "#FFFFFF", 22);
  const d = circleLabel(s, "Прогноз", 950, 245, 130, C.green, "#FFFFFF", 22);
  addText(s, "Классификация", 100, 475, 250, 38, { size: 26, bold: true, color: C.indigo });
  addText(s, "категория\nспам / не спам\nсдаст / не сдаст", 100, 520, 260, 95, { size: 20, color: C.muted, lineSpacing: 1.15 });
  addShape(s, "rect", 580, 465, 2, 150, C.pale2, "none");
  addText(s, "Регрессия", 680, 475, 250, 38, { size: 26, bold: true, color: C.indigo });
  addText(s, "число\nцена дома\nитоговый балл", 680, 520, 260, 95, { size: 20, color: C.muted, lineSpacing: 1.15 });
  addFooter(s, 8);
  addNotes(s, "Примеры: классификация — сдаст ли студент экзамен; регрессия — итоговый балл.", "Текст пользователя для слайда 8.");
}

// 9 — Unsupervised learning.
{
  const s = deck.slides.add();
  s.background.fill = C.paper;
  addHeader(s, "08", "Без учителя: модель сама находит структуру");
  addText(s, "Данные не имеют готовых ответов. Алгоритм ищет скрытые закономерности.", 72, 186, 580, 80, { size: 26, color: C.ink, lineSpacing: 1.15 });
  addText(s, "Кластеризация", 72, 315, 240, 34, { size: 25, bold: true, color: C.indigo });
  addText(s, "• сегменты клиентов\n• группы документов\n• студенты по успеваемости", 72, 360, 370, 120, { size: 21, color: C.muted, lineSpacing: 1.18 });
  addText(s, "Снижение размерности", 72, 520, 300, 34, { size: 25, bold: true, color: C.indigo });
  addText(s, "упрощение сложных данных", 72, 562, 330, 30, { size: 20, color: C.muted });
  addShape(s, "rect", 650, 205, 520, 390, C.pale, "none", 24);
  const dots = [
    [720,270,C.blue],[758,310,C.blue],[695,335,C.blue],[775,365,C.blue],[735,390,C.blue],
    [930,255,C.orange],[970,290,C.orange],[910,330,C.orange],[990,345,C.orange],[950,385,C.orange],
    [830,445,C.green],[875,465,C.green],[805,500,C.green],[900,520,C.green],[850,545,C.green],
  ];
  dots.forEach(([x,y,c],i)=>addShape(s,"ellipse",x,y,18 + (i%3)*4,18 + (i%3)*4,c,"none"));
  addText(s, "3 кластера", 835, 608, 180, 28, { size: 18, bold: true, color: C.indigo, align: "center" });
  addFooter(s, 9);
  addNotes(s, "Визуальный якорь показывает, как точки объединяются в три группы.", "Текст пользователя для слайда 9.");
}

// 10 — Reinforcement learning.
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  addHeader(s, "09", "С подкреплением: действие оценивается наградой");
  addText(s, "Агент действует в среде и учится выбирать стратегию с лучшим долгосрочным результатом.", 72, 182, 850, 64, { size: 25, color: C.muted, lineSpacing: 1.1 });
  arrow(s, 350, 340, 90, 34, C.orange);
  arrow(s, 680, 340, 90, 34, C.orange);
  addShape(s, "downArrow", 930, 430, 34, 68, C.blue, "none");
  circleLabel(s, "Агент", 120, 285, 160, C.indigo, "#FFFFFF", 27);
  circleLabel(s, "Действие", 470, 285, 160, C.orange, C.indigo, 25);
  circleLabel(s, "Среда", 800, 285, 160, C.blue, "#FFFFFF", 27);
  circleLabel(s, "+ / −", 890, 485, 120, C.green, "#FFFFFF", 32);
  addText(s, "награда / штраф", 850, 615, 220, 26, { size: 18, bold: true, color: C.green, align: "center" });
  addText(s, "Где используется", 72, 515, 230, 30, { size: 21, bold: true, color: C.orange });
  addText(s, "Игры • робототехника • рекомендательные системы", 72, 560, 570, 50, { size: 23, bold: true, color: C.indigo });
  addText(s, "Пример: робот получает штраф за падение и награду за устойчивое движение.", 72, 625, 710, 30, { size: 19, color: C.muted });
  addFooter(s, 10);
  addNotes(s, "Цикл: агент выбирает действие, среда возвращает награду или штраф.", "Текст пользователя для слайда 10.");
}

// 11 — Lifecycle.
{
  const s = deck.slides.add();
  s.background.fill = C.paper;
  addHeader(s, "10", "Жизненный цикл модели: пять шагов");
  const xs = [75, 315, 555, 795, 1035];
  for (let i = 0; i < 4; i++) arrow(s, xs[i] + 145, 335, 55, 24, C.orange);
  const steps = [
    ["1", "Сбор данных", "откуда берём информацию"],
    ["2", "Очистка", "ошибки, дубликаты, пустоты"],
    ["3", "Разбивка", "70% обучение / 30% проверка"],
    ["4", "Обучение", "алгоритм ищет закономерности"],
    ["5", "Оценка", "качество на новых данных"],
  ];
  steps.forEach((st, i) => {
    circleLabel(s, st[0], xs[i], 286, 115, i === 4 ? C.orange : C.indigo, i === 4 ? C.indigo : "#FFFFFF", 34);
    addText(s, st[1], xs[i] - 25, 430, 165, 40, { size: 23, bold: true, color: C.ink, align: "center" });
    addText(s, st[2], xs[i] - 30, 482, 175, 72, { size: 18, color: C.muted, align: "center", lineSpacing: 1.12 });
  });
  addText(s, "Проверка на новых данных показывает, будет ли модель работать за пределами учебной выборки.", 215, 604, 850, 40, { size: 22, bold: true, color: C.indigo, align: "center" });
  addFooter(s, 11);
  addNotes(s, "Разбивка 70/30 показана как учебный пример, а не универсальное правило.", "Текст пользователя для слайда 11.");
}

// 12 — Comparison table.
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  addHeader(s, "11", "Вид обучения зависит от доступного сигнала");
  const values = [
    ["Вид обучения", "Правильные ответы", "Главная задача", "Пример"],
    ["С учителем", "Есть: разметка", "Предсказать метку или число", "Классификация спама"],
    ["Без учителя", "Нет: сырые данные", "Найти группы и паттерны", "Сегменты клиентов"],
    ["С подкреплением", "Награда / штраф", "Найти долгосрочную стратегию", "Шахматы"],
  ];
  const table = s.tables.add({ rows: 4, columns: 4, left: 64, top: 210, width: 1152, height: 350, values, columnWidths: [245, 245, 385, 277] });
  table.borders.assign({ style: "solid", fill: "#D6DCE9", width: 1 });
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 4 }).assign({ fill: C.indigo, textStyle: { typeface: "Arial", fontSize: 20, bold: true, color: "#FFFFFF" }, margins: { left: 16, right: 12, top: 10, bottom: 10 }, anchor: "middle" });
  for (let r = 1; r < 4; r++) {
    table.cells.block({ row: r, column: 0, rowCount: 1, columnCount: 4 }).assign({ fill: r % 2 ? "#FFFFFF" : "#EEF1F7", textStyle: { typeface: "Arial", fontSize: 19, color: C.ink }, margins: { left: 16, right: 12, top: 10, bottom: 10 }, anchor: "middle" });
    table.getCell(r,0).text.style = { typeface: "Arial", fontSize: 20, bold: true, color: r === 1 ? C.orange : C.indigo };
  }
  addText(s, "Сначала спросите: какой обучающий сигнал доступен?", 300, 610, 680, 40, { size: 23, bold: true, color: C.indigo, align: "center" });
  addFooter(s, 12);
  addNotes(s, "Таблица сравнивает разметку, задачу и реальный пример.", "Текст пользователя для слайда 12.");
}

// 13 — Return to the student case.
{
  const s = deck.slides.add();
  s.background.fill = C.paper;
  addHeader(s, "12", "Кейс со студентами: три задачи — три ответа");
  const rows = [
    ["1", "Спрогнозировать итоговый балл", "Регрессия", "результат — число"],
    ["2", "Определить, сдаст ли студент экзамен", "Классификация", "результат — класс Да / Нет"],
    ["3", "Объединить студентов по успеваемости", "Кластеризация", "группы без заранее заданных названий"],
  ];
  rows.forEach((r, i) => {
    const y = 205 + i * 145;
    circleLabel(s, r[0], 75, y, 72, i === 0 ? C.orange : C.indigo, i === 0 ? C.indigo : "#FFFFFF", 28);
    addText(s, r[1], 185, y - 2, 500, 48, { size: 24, bold: true, color: C.ink, valign: "middle" });
    arrow(s, 700, y + 18, 60, 24, C.orange);
    addText(s, r[2], 800, y - 4, 270, 45, { size: 26, bold: true, color: C.indigo, valign: "middle" });
    addText(s, r[3], 800, y + 48, 360, 35, { size: 18, color: C.muted });
    if (i < 2) addShape(s, "rect", 185, y + 112, 900, 1, C.pale2, "none");
  });
  addFooter(s, 13);
  addNotes(s, "Возврат к задаче со слайда 4 закрепляет различия между типами задач.", "Текст пользователя для слайда 13.");
}

// 14 — Summary.
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  addHeader(s, "13", "Три мысли, которые стоит запомнить");
  addText(s, "3", 80, 205, 260, 300, { size: 230, bold: true, color: C.orange, align: "center", valign: "middle" });
  addText(s, "ML строит модели на основе данных, а не набора жёстких правил.", 420, 205, 720, 80, { size: 29, bold: true, color: C.indigo, lineSpacing: 1.05 });
  addShape(s, "rect", 420, 310, 720, 2, C.pale2, "none");
  addText(s, "Тип обучения выбирают по тому, есть ли разметка, скрытая структура или награда.", 420, 345, 720, 100, { size: 28, bold: true, color: C.indigo, lineSpacing: 1.05 });
  addShape(s, "rect", 420, 470, 720, 2, C.pale2, "none");
  addText(s, "Классификация предсказывает категорию. Регрессия — число.", 420, 505, 720, 90, { size: 28, bold: true, color: C.indigo, lineSpacing: 1.05 });
  addFooter(s, 14);
  addNotes(s, "Итоги сведены к трём правилам выбора и различения задач.", "Текст пользователя для слайда 14.");
}

// 15 — Audience question.
{
  const s = deck.slides.add();
  s.background.fill = C.indigo;
  addText(s, "ИТОГОВЫЙ ВОПРОС", 72, 58, 320, 28, { size: 17, bold: true, color: C.orange2 });
  addText(s, "Если вы хотите, чтобы компьютер научился отличать кошек от собак на фото, какой вид обучения вам нужно использовать — с учителем или без?", 72, 135, 1040, 260, { size: 43, bold: true, color: "#FFFFFF", lineSpacing: 1.03 });
  addText(s, "С учителем", 150, 495, 360, 90, { size: 30, bold: true, color: C.indigo, fill: C.orange, geometry: "roundRect", radius: 24, align: "center", valign: "middle" });
  addText(s, "Без учителя", 690, 495, 360, 90, { size: 30, bold: true, color: "#FFFFFF", fill: "#3A4D7C", geometry: "roundRect", radius: 24, align: "center", valign: "middle", line: { style: "solid", fill: "#8292BD", width: 2 } });
  addText(s, "Почему?", 495, 625, 290, 38, { size: 22, bold: true, color: C.orange2, align: "center" });
  addFooter(s, 15, true);
  addNotes(s, "Ответ для ведущего: с учителем, потому что нужны заранее размеченные фотографии с метками «кот» и «собака».", "Текст пользователя для слайда 15.");
}

await fs.mkdir(PREVIEW, { recursive: true });
for (const [i, slide] of deck.slides.items.entries()) {
  const stem = `slide-${String(i + 1).padStart(2, "0")}`;
  const png = await deck.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(`${PREVIEW}/${stem}.png`, new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(`${PREVIEW}/${stem}.layout.json`, await layout.text());
}
const montage = await deck.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(`${PREVIEW}/montage.webp`, new Uint8Array(await montage.arrayBuffer()));
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(OUT);
console.log(OUT);
