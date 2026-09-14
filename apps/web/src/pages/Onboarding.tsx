import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '@investiq/api-client';
import { Button } from '../components/ui/Button';

// Types and Questions
type Question = {
  id: string;
  title: string;
  options: { label: string; value: string | number }[];
};

const questions: Question[] = [
  {
    id: 'age',
    title: 'How old are you?',
    options: [
      { label: 'Under 30 (Long-term growth focus)', value: 25 },
      { label: '30 to 50 (Balanced approach)', value: 40 },
      { label: 'Over 50 (Capital preservation focus)', value: 55 },
    ],
  },
  {
    id: 'investment_goal',
    title: 'What is your primary goal for this money?',
    options: [
      { label: 'Grow it as much as possible, even with volatility', value: 'growth' },
      { label: 'Earn steady extra income over time', value: 'income' },
      { label: 'Protect my savings from losing value', value: 'preservation' },
    ],
  },
  {
    id: 'risk_tolerance',
    title: 'If your investment dropped 15% in a single month, what would you do?',
    options: [
      { label: 'Buy more while the price is low', value: 'high' },
      { label: 'Wait and do nothing, the market will recover', value: 'medium' },
      { label: 'Sell everything to avoid further losses', value: 'low' },
    ],
  },
  {
    id: 'time_horizon',
    title: 'When do you think you will need to withdraw this money?',
    options: [
      { label: 'More than 5 years from now', value: 'long' },
      { label: 'In 2 to 5 years', value: 'medium' },
      { label: 'Within the next year', value: 'short' },
    ],
  },
];

export const Onboarding = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resultCategory, setResultCategory] = useState<string | null>(null);

  const handleSelect = async (value: string | number) => {
    const newAnswers = { ...answers, [questions[currentStep].id]: value };
    setAnswers(newAnswers);

    if (currentStep < questions.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      // Submit
      try {
        setIsSubmitting(true);
        const profile = await auth.saveRiskProfile(newAnswers);
        setResultCategory(profile.category);
      } catch (error) {
        console.error('Failed to save risk profile', error);
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  if (resultCategory) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-lg space-y-6 bg-white p-8 rounded-xl shadow-sm border border-gray-100 text-center">
          <div className="mx-auto w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-6">
            <span className="text-2xl">🎯</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-gray-900">
            You are a {resultCategory.charAt(0).toUpperCase() + resultCategory.slice(1)} Investor
          </h2>
          <p className="text-gray-600 leading-relaxed">
            {resultCategory === 'aggressive' && "You're comfortable with market ups and downs to chase higher long-term returns. We'll suggest a portfolio heavily focused on high-growth PSX stocks."}
            {resultCategory === 'moderate' && "You prefer a balanced approach. You want growth, but not at the cost of losing sleep. We'll suggest a mix of stable dividend payers and moderate-growth stocks."}
            {resultCategory === 'conservative' && "Protecting your money is your top priority. You prefer slow, steady gains over risky bets. We'll focus on highly stable, low-volatility blue-chip stocks."}
          </p>
          <Button className="w-full mt-6" onClick={() => navigate('/dashboard')}>
            Go to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const question = questions[currentStep];
  const progress = ((currentStep + 1) / questions.length) * 100;

  return (
    <div className="flex min-h-screen flex-col items-center pt-20 bg-gray-50 px-4">
      <div className="w-full max-w-lg">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-600 transition-all duration-300 ease-out" 
              style={{ width: `${progress}%` }} 
            />
          </div>
          <p className="mt-2 text-xs text-gray-500 font-medium text-right uppercase tracking-wider">
            Step {currentStep + 1} of {questions.length}
          </p>
        </div>

        {/* Question Area */}
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900 leading-tight">
            {question.title}
          </h2>

          <div className="space-y-3 mt-8">
            {question.options.map((option, idx) => (
              <button
                key={idx}
                onClick={() => handleSelect(option.value)}
                disabled={isSubmitting}
                className="w-full text-left p-4 rounded-xl border-2 border-gray-100 bg-white hover:border-blue-500 hover:bg-blue-50 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 group"
              >
                <div className="flex items-center">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full border-2 border-gray-300 group-hover:border-blue-500 mr-4" />
                  <span className="text-gray-700 font-medium group-hover:text-gray-900">
                    {option.label}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Footer actions */}
        <div className="mt-12 flex justify-between items-center h-10">
          {currentStep > 0 ? (
            <button
              onClick={handleBack}
              className="text-gray-500 hover:text-gray-900 text-sm font-medium transition-colors"
            >
              ← Back
            </button>
          ) : (
            <div /> // Spacer
          )}
          {isSubmitting && <span className="text-sm text-gray-500 animate-pulse">Saving profile...</span>}
        </div>
      </div>
    </div>
  );
};
