"""
Human-in-the-Loop Agent for clarifications and confirmations.
"""

from typing import Dict, Any, Optional, List, Callable

from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class HumanLoopAgent:
    """
    Agent for human-in-the-loop interactions.
    Asks clarifying questions and gets user input when needed.
    """

    def __init__(self, input_callback: Optional[Callable[[str], str]] = None):
        """
        Initialize HumanLoopAgent.

        Args:
            input_callback: Function to get user input (defaults to input())
        """
        self.input_callback = input_callback or self._default_input
        logger.info("Initialized HumanLoopAgent")

    def _default_input(self, prompt: str) -> str:
        """Default input method using built-in input()"""
        return input(prompt)

    @trace_function("ask_clarification")
    def ask_clarification(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ask user for clarification.

        Args:
            question: Clarification question
            context: Additional context
            suggestions: Optional list of suggestions

        Returns:
            User's response
        """
        try:
            # Format the question
            formatted_question = f"\n{question}\n"

            if suggestions:
                formatted_question += "\nSuggestions:\n"
                for i, suggestion in enumerate(suggestions, 1):
                    formatted_question += f"  {i}. {suggestion}\n"

            formatted_question += "\nYour response: "

            # Get user input
            user_response = self.input_callback(formatted_question)

            logger.info("Received user clarification", response_length=len(user_response))

            return {
                "success": True,
                "response": user_response.strip(),
                "question": question,
            }

        except Exception as e:
            logger.error(f"Failed to get user input: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @trace_function("ask_confirmation")
    def ask_confirmation(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Ask user to confirm an action.

        Args:
            action: Description of action to confirm
            details: Optional additional details

        Returns:
            True if confirmed, False otherwise
        """
        try:
            prompt = f"\n{action}\n"

            if details:
                prompt += "\nDetails:\n"
                for key, value in details.items():
                    prompt += f"  {key}: {value}\n"

            prompt += "\nProceed? (yes/no): "

            response = self.input_callback(prompt).strip().lower()

            confirmed = response in ["yes", "y", "true", "1"]

            logger.info(f"User confirmation: {confirmed}")

            return confirmed

        except Exception as e:
            logger.error(f"Failed to get confirmation: {e}")
            return False

    @trace_function("ask_choice")
    def ask_choice(
        self,
        question: str,
        choices: List[str],
        allow_custom: bool = False,
    ) -> Optional[str]:
        """
        Ask user to select from multiple choices.

        Args:
            question: Question to ask
            choices: List of choices
            allow_custom: Allow custom response

        Returns:
            Selected choice or None
        """
        try:
            prompt = f"\n{question}\n\n"

            for i, choice in enumerate(choices, 1):
                prompt += f"  {i}. {choice}\n"

            if allow_custom:
                prompt += f"  {len(choices) + 1}. Other (please specify)\n"

            prompt += "\nSelect option number: "

            response = self.input_callback(prompt).strip()

            # Try to parse as number
            try:
                choice_num = int(response)
                if 1 <= choice_num <= len(choices):
                    selected = choices[choice_num - 1]
                    logger.info(f"User selected option {choice_num}: {selected}")
                    return selected
                elif allow_custom and choice_num == len(choices) + 1:
                    custom_response = self.input_callback("Please specify: ").strip()
                    logger.info(f"User provided custom choice: {custom_response}")
                    return custom_response
                else:
                    logger.warning(f"Invalid choice number: {choice_num}")
                    return None

            except ValueError:
                # Not a number, treat as custom if allowed
                if allow_custom:
                    logger.info(f"User provided direct response: {response}")
                    return response
                else:
                    logger.warning(f"Invalid choice: {response}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get choice: {e}")
            return None

    @trace_function("provide_suggestions")
    def provide_suggestions(
        self,
        context: str,
        suggestions: List[str],
    ) -> Dict[str, Any]:
        """
        Provide suggestions to the user without requiring immediate input.

        Args:
            context: Context for the suggestions
            suggestions: List of suggestions

        Returns:
            Acknowledgment
        """
        message = f"\n{context}\n\nSuggestions:\n"

        for i, suggestion in enumerate(suggestions, 1):
            message += f"  {i}. {suggestion}\n"

        print(message)

        logger.info("Provided suggestions to user", num_suggestions=len(suggestions))

        return {
            "success": True,
            "message_delivered": True,
        }

    @trace_function("notify")
    def notify(self, message: str, level: str = "INFO"):
        """
        Notify user with a message.

        Args:
            message: Message to display
            level: Level (INFO, WARNING, ERROR)
        """
        prefix = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
        }.get(level, "ℹ️")

        formatted_message = f"\n{prefix} {message}\n"
        print(formatted_message)

        logger.info(f"Notified user", level=level)


# Global human loop agent
_human_loop_agent = None


def get_human_loop_agent(
    input_callback: Optional[Callable[[str], str]] = None,
) -> HumanLoopAgent:
    """Get global human loop agent"""
    global _human_loop_agent
    if _human_loop_agent is None:
        _human_loop_agent = HumanLoopAgent(input_callback=input_callback)
    return _human_loop_agent
