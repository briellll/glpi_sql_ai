"""
Módulo de memória conversacional.
Gerencia o histórico de interações entre turnos para contexto em prompts.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Gerencia o histórico da conversa entre turnos."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.turns: list[dict[str, Any]] = []

    def add_turn(self, question: str, answer: str, intent: str) -> None:
        """
        Registra um turno da conversa.

        Args:
            question: Pergunta do usuário
            answer: Resposta do assistente
            intent: Intenção classificada (database_query | get_solutions)
        """
        self.turns.append({
            "question": question,
            "answer": answer,
            "intent": intent,
        })
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_context(self, max_recent: int = 3) -> str:
        """
        Retorna o histórico formatado para injeção em prompts.

        Args:
            max_recent: Número máximo de turnos recentes a incluir

        Returns:
            String formatada com o histórico ou string vazia
        """
        if not self.turns:
            return ""

        lines = [
            "## Histórico da Conversa (para contexto de perguntas anteriores):"
        ]
        for turn in self.turns[-max_recent:]:
            lines.append(f"Usuário: {turn['question']}")
            lines.append(f"Assistente: {turn['answer']}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Limpa todo o histórico."""
        self.turns.clear()
