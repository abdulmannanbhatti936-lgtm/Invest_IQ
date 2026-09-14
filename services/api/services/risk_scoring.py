from models.risk_profile import RiskCategory

def calculate_risk_category(answers: dict) -> RiskCategory:
    """
    Pure function to calculate risk category based on answers.
    Answers should be a dictionary with specific keys mapped to scores.
    Example:
    {
        "age": 25, # younger = higher risk tolerance
        "investment_goal": "growth", # growth, income, preservation
        "risk_tolerance": "high", # high, medium, low
        "time_horizon": "long" # long, medium, short
    }
    """
    score = 0
    
    # 1. Age
    age = answers.get("age", 35)
    if isinstance(age, int):
        if age < 30:
            score += 3
        elif age < 50:
            score += 2
        else:
            score += 1
            
    # 2. Investment Goal
    goal = answers.get("investment_goal", "").lower()
    if goal == "growth":
        score += 3
    elif goal == "income":
        score += 2
    elif goal == "preservation":
        score += 1
        
    # 3. Risk Tolerance
    tolerance = answers.get("risk_tolerance", "").lower()
    if tolerance == "high":
        score += 3
    elif tolerance == "medium":
        score += 2
    elif tolerance == "low":
        score += 1
        
    # 4. Time Horizon
    horizon = answers.get("time_horizon", "").lower()
    if horizon == "long":
        score += 3
    elif horizon == "medium":
        score += 2
    elif horizon == "short":
        score += 1
        
    # Classification
    # Max score is 12, min is 4 (assuming all fields provided)
    if score >= 10:
        return RiskCategory.aggressive
    elif score >= 7:
        return RiskCategory.moderate
    else:
        return RiskCategory.conservative
