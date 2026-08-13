import { describe, expect, it } from "vitest";

import { targetLabel } from "./admin-app";

describe("moderation target copy", () => {
  it.each([
    ["event", "photo", "Фотография события"],
    ["profile", "avatar", "Аватар профиля"],
    ["looking_post", "title", "Название идеи"],
    ["q_and_a_answer", "answer", "Текст ответа в Q&A"],
    ["chat_message", "message", "Сообщение чата"],
  ])("labels %s.%s naturally", (subject, component, expected) => {
    expect(targetLabel(subject, component)).toBe(expected);
  });

  it("does not expose unknown technical codes", () => {
    expect(targetLabel("future_subject", "raw_component")).toBe(
      "Неизвестная цель",
    );
  });
});
