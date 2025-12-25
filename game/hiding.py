"""Escape mechanics with prediction-based AI integration."""
from typing import Dict, List, Any
from game.config_loader import config


class HidingManager:
    """Manages escape options (hiding spots + escape routes) for prediction-based mechanics."""

    def __init__(self):
        """Initialize HidingManager with config data."""
        self.mechanics_config = config.get_hiding_mechanics()
        if not self.mechanics_config:
            # Defaults if config not loaded
            self.mechanics_config = {
                'run_point_retention': 0.8
            }
        self.escape_options = config.get_escape_options()

    def get_escape_options_for_location(self, location_name: str) -> List[Dict[str, Any]]:
        """
        Get all escape options (hiding spots + escape routes) for a location.

        Args:
            location_name: Name of the location (e.g., "Corner Store")

        Returns:
            List of escape option dicts with id, name, description, emoji, type
        """
        return self.escape_options.get(location_name, [])

    def get_hiding_spots_for_location(self, location_name: str) -> List[Dict[str, Any]]:
        """
        Get only hiding spots for a location (backward compatibility).

        Args:
            location_name: Name of the location

        Returns:
            List of hiding spot dicts (type == 'hide')
        """
        options = self.get_escape_options_for_location(location_name)
        return [opt for opt in options if opt.get('type', 'hide') == 'hide']

    def get_escape_routes_for_location(self, location_name: str) -> List[Dict[str, Any]]:
        """
        Get only escape routes for a location.

        Args:
            location_name: Name of the location

        Returns:
            List of escape route dicts (type == 'run')
        """
        options = self.get_escape_options_for_location(location_name)
        return [opt for opt in options if opt.get('type') == 'run']

    def resolve_escape_attempt(
        self,
        player_choice: Dict[str, Any],
        ai_prediction: str,
        location_points: int
    ) -> Dict[str, Any]:
        """
        Resolve an escape attempt based on prediction matching.

        The player escapes if their choice differs from the AI's prediction.
        Both hiding and running escapes retain 80% of location points.

        Args:
            player_choice: The escape option dict the player selected
            ai_prediction: The option ID the AI predicted
            location_points: Points rolled at this location

        Returns:
            Dict with:
                - escaped: bool - True if player outsmarted the AI
                - points_awarded: int - Points player keeps (80% on successful escape)
                - player_choice_id: str - What player chose
                - ai_prediction_id: str - What AI predicted
                - choice_type: str - 'hide' or 'run'
                - ai_was_correct: bool - True if AI guessed right
        """
        player_option_id = player_choice['id']
        choice_type = player_choice.get('type', 'hide')

        # Core mechanic: Did the player outsmart the AI?
        escaped = (player_option_id != ai_prediction)

        # Calculate points based on outcome (hiding and running both retain points)
        points_awarded = 0
        if escaped:
            retention = self.get_option_keep_amount(player_choice)
            points_awarded = int(location_points * retention)

        return {
            'escaped': escaped,
            'points_awarded': points_awarded,
            'player_choice_id': player_option_id,
            'player_choice_name': player_choice.get('name', player_option_id),
            'ai_prediction_id': ai_prediction,
            'choice_type': choice_type,
            'ai_was_correct': not escaped,
            'location_points': location_points
        }

    def get_run_point_retention(self) -> float:
        """
        Get the percentage of points retained when running successfully.

        Returns:
            Point retention ratio (default 0.8 = 80%)
        """
        return self.mechanics_config.get('run_point_retention', 0.8)

    def get_option_keep_amount(self, option: Dict[str, Any]) -> float:
        """
        Get the point retention for a specific escape option.

        Args:
            option: The escape option dict

        Returns:
            Point retention ratio (0.0-1.0), defaults to global run_point_retention
        """
        return option.get('keep_amount', self.get_run_point_retention())

    def get_option_by_id(self, location_name: str, option_id: str) -> Dict[str, Any]:
        """
        Get a specific escape option by its ID.

        Args:
            location_name: Name of the location
            option_id: ID of the escape option

        Returns:
            The escape option dict, or empty dict if not found
        """
        options = self.get_escape_options_for_location(location_name)
        for opt in options:
            if opt['id'] == option_id:
                return opt
        return {}
