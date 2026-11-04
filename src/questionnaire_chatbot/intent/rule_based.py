"""Conservative whole-utterance Korean command parser.

classify preserves the existing string-returning Protocol. parse adds targets.
No answers are inferred and no actions are executed. FINISH is only a request:
future integration must route it through review, never directly confirm finish.
Unlisted paraphrases return UNKNOWN rather than a guessed command.
"""

import re
import unicodedata

from .schemas import Intent, ParseResult, ParseStatus, TargetReference

# Whitespace is ignored, including spacing variations around Korean particles.
# Only sentence-final punctuation is stripped; internal clause boundaries remain.
def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).rstrip(".!?。！？")


PATTERNS = {
    Intent.NEXT: (r"다음", r"다음(?:질문|문항)(?:으로)?(?:넘어가|이동해|가)(?:줘|주세요|줄래|줄래요)?", r"다음(?:질문|문항)(?:을)?보여(?:줘|주세요)", r"다음으로(?:가자|가요|가주세요|넘어가줘)"),
    Intent.PREVIOUS: (r"이전", r"(?:이전|전)(?:질문|문항)(?:을)?(?:다시)?보여(?:줘|주세요)", r"아까질문다시보여(?:줘|주세요)", r"(?:이전|전)(?:질문|문항)으로(?:돌아가|가)(?:줘|주세요|고싶어|고싶어요|ㄹ래)?"),
    Intent.SKIP: (r"건너뛰기", r"(?:이질문|이번문항)(?:은)?(?:건너뛸게|건너뛸게요|패스할게|패스할게요)", r"모르겠으니까넘어갈래(?:요)?", r"(?:이질문|이번문항)(?:을)?건너뛰어(?:줘|주세요)"),
    Intent.EDIT: (r"방금답변(?:을)?수정(?:할게|할게요|하고싶어|하고싶어요)", r"이전에선택한답(?:을)?바꾸고싶어(?:요)?", r"(?:현재|이전)(?:질문|문항)의?답변(?:을)?수정(?:할래|할래요|해줘|해주세요)"),
    Intent.PROGRESS: (r"지금몇번째질문(?:이야|인가요)", r"설문얼마나진행했(?:어|나요)", r"몇개남았(?:어|나요)", r"진행상황(?:을)?보여(?:줘|주세요)"),
    Intent.SHOW_ANSWER: (r"내가앞에서뭐라고답했(?:지|나요)", r"현재(?:질문|문항)의?답변(?:을)?보여(?:줘|주세요)", r"이전(?:질문|문항)의?답변(?:을)?보여(?:줘|주세요)"),
    Intent.REVIEW: (r"답변전체(?:를)?검토하고싶어(?:요)?", r"최종검토화면(?:을)?보여(?:줘|주세요)", r"최종검토"),
    Intent.FINISH: (r"설문(?:을)?끝내고싶어(?:요)?", r"이제설문마칠게(?:요)?", r"설문종료"),
}

NUMBERED = (
    (Intent.GOTO, r"(?P<number>[+-]?\d+)번(?:질문|문항)(?:으로)?(?:(?:이동해|돌아가|가)(?:줘|주세요|고싶어|고싶어요)?|돌아갈래(?:요)?)"),
    (Intent.GOTO, r"(?P<number>[+-]?\d+)번(?:질문|문항)(?:을)?보여(?:줘|주세요)"),
    (Intent.EDIT, r"(?P<number>[+-]?\d+)번(?:질문|문항)의?답변(?:을)?수정(?:할래|할래요|해줘|해주세요|하고싶어|하고싶어요)"),
    (Intent.SHOW_ANSWER, r"(?P<number>[+-]?\d+)번(?:질문|문항)에뭐라고답했(?:어|나요)"),
    (Intent.SHOW_ANSWER, r"(?P<number>[+-]?\d+)번(?:질문|문항)의?답변(?:을)?보여(?:줘|주세요)"),
)


class RuleBasedIntentParser:
    def classify(self, text: str) -> str:
        return self.parse(text).intent.value

    def parse(self, text: str) -> ParseResult:
        if not isinstance(text, str):
            raise TypeError("입력은 문자열이어야 합니다.")
        normalized = _normalize(text)

        def result(intent, number=None, reference=None):
            status = (ParseStatus[intent.value] if intent in
                      (Intent.UNKNOWN, Intent.AMBIGUOUS, Intent.REJECTED) else ParseStatus.MATCHED)
            return ParseResult(intent, number, reference, text, status)

        # Negative requests are never interpreted as positive commands.
        if re.search(r"(?:가지마|넘어가지마|이동하지마|돌아가지마|수정하지마|바꾸지마|건너뛰지마|끝내지마|마치지마|보여주지마|하지마|말아|말고|싫어|않아|않을|않겠|안할|안해)", normalized):
            return result(Intent.REJECTED)
        if re.fullmatch(r"\d+번(?:으로)?", normalized):
            return result(Intent.AMBIGUOUS)

        # Reject potential multi-command utterances as a unit, even when one
        # clause is not itself one of our exact supported command patterns.
        clauses = re.split(r"그리고|그다음|그런다음|[,.!?;]", normalized)
        if len(clauses) > 1:
            recognized = sum(
                any(re.fullmatch(pattern, clause) for patterns in PATTERNS.values() for pattern in patterns)
                or any(re.fullmatch(pattern, clause) for _, pattern in NUMBERED)
                for clause in clauses if clause
            )
            if recognized >= 2:
                return result(Intent.AMBIGUOUS)
        command_markers = re.findall(r"이동|돌아가|넘어가|보여|건너뛰|건너뛸|패스|수정|바꾸|바꿀|검토|끝내|마칠|가서", normalized)

        for intent, pattern in NUMBERED:
            match = re.fullmatch(pattern, normalized)
            if match:
                digits = match.group("number")
                # Avoid converting arbitrarily long integers from untrusted text.
                if len(digits) > 3:
                    return result(Intent.REJECTED)
                number = int(digits)
                if not 1 <= number <= 11:
                    return result(Intent.REJECTED, number)
                return result(intent, number)

        matches = [intent for intent, patterns in PATTERNS.items()
                   if any(re.fullmatch(pattern, normalized) for pattern in patterns)]
        if len(matches) != 1:
            return result(Intent.AMBIGUOUS if matches or len(command_markers) >= 2 else Intent.UNKNOWN)
        intent = matches[0]
        reference = None
        if intent == Intent.EDIT:
            reference = (TargetReference.CURRENT if normalized.startswith("현재") else
                         TargetReference.PREVIOUS if normalized.startswith("이전질문") or normalized.startswith("이전문항") else TargetReference.LAST_ANSWER)
        elif intent == Intent.SHOW_ANSWER:
            reference = (TargetReference.CURRENT if normalized.startswith("현재") else
                         TargetReference.PREVIOUS if normalized.startswith("이전") else TargetReference.LAST_ANSWER)
        elif intent == Intent.PREVIOUS:
            reference = TargetReference.PREVIOUS
        elif intent == Intent.SKIP:
            reference = TargetReference.CURRENT
        return result(intent, reference=reference)
