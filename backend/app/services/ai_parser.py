#import json
#import logging
#from decimal import Decimal
#
#import anthropic
#from pydantic import ValidationError
#
#from app.config import get_settings
#from app.schemas import ParsedPayee, ParsedPayouts
#
#logger = logging.getLogger(__name__)
#settings = get_settings()
#
#
#class AIParser:
#    def __init__(self, client: anthropic.Anthropic | None = None):
#        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
#        self.model = settings.anthropic_model
#        self._system_prompt = self._load_system_prompt()
#
#    def _load_system_prompt(self) -> str:
#        try:
#            with open("backend/app/prompts/parser_system.md") as f:
#                return f.read()
#        except FileNotFoundError:
#            logger.warning("Parser system prompt not found, using default")
#            return "Extract payees from input. Return JSON array with name, email, amount, currency, note."
#
#    def parse(self, raw_input: str, is_csv: bool = False) -> ParsedPayouts:
#        """
#        Parse raw CSV or text input into structured payees.
#        Retries once on validation failure.
#        """
#        user_prompt = self._build_user_prompt(raw_input, is_csv)
#
#        for attempt in range(2):
#            try:
#                response = self.client.messages.create(  # type: ignore[call-overload]
#                    model=self.model,
#                    max_tokens=4096,
#                    system=self._system_prompt,
#                    messages=[{"role": "user", "content": user_prompt}],
#                )
#                content = response.content[0].text
#                parsed = self._parse_and_validate(content)
#                logger.info(f"Successfully parsed {len(parsed.payees)} payees on attempt {attempt + 1}")
#                return parsed
#            except (json.JSONDecodeError, ValidationError) as e:
#                logger.warning(f"Parse attempt {attempt + 1} failed: {e}")
#                if attempt == 1:
#                    raise ValueError(f"Failed to parse after 2 attempts: {e}") from e
#
#        raise ValueError("Unexpected parse failure")
#
#    def _build_user_prompt(self, raw_input: str, is_csv: bool) -> str:
#        if is_csv:
#            return f"Parse this CSV into payees:\n```\n{raw_input}\n```"
#        return f"Parse this free-text payout instruction:\n```\n{raw_input}\n```"
#
#    def _parse_and_validate(self, content: str) -> ParsedPayouts:
#        data = json.loads(content)
#
#        if isinstance(data, list):
#            payees_data = data
#        elif isinstance(data, dict) and "payees" in data:
#            payees_data = data["payees"]
#        else:
#            raise ValueError(f"Unexpected response format: {type(data)}")
#
#        payees = []
#        for p in payees_data:
#            amount = Decimal(str(p.get("amount", "0")))
#            payees.append(
#                ParsedPayee(
#                    name=p.get("name", "").strip(),
#                    email=p.get("email", "").strip().lower(),
#                    amount=amount,
#                    currency=p.get("currency", "USD").upper(),
#                    note=p.get("note"),
#                )
#            )
#
#        return ParsedPayouts(
#            payees=payees,
#            raw_input_summary=f"Parsed {len(payees)} payees",
#        )
#
#
#def parse_payouts(raw_input: str, is_csv: bool = False) -> ParsedPayouts:
#    """Convenience function for single-use parsing."""
#    parser = AIParser()
#    return parser.parse(raw_input, is_csv)
