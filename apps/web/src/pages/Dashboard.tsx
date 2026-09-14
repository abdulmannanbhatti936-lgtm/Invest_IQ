import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/Button';
import { Briefcase } from 'lucide-react';

export const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // In a real app, we'd check if they have a generated portfolio or not.
  // For Step 1.7, we are specifically building the empty state.
  const hasPortfolio = false; 

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {user?.full_name?.split(' ')[0] || 'Investor'}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Here is what's happening with your investments today.
        </p>
      </div>

      {!hasPortfolio ? (
        // Designed Empty State (Design.md §12.2)
        <div className="flex flex-col items-center justify-center p-12 mt-8 text-center bg-white border border-gray-200 border-dashed rounded-xl shadow-sm">
          <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
            <Briefcase className="w-8 h-8 text-blue-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            No Portfolio Generated Yet
          </h3>
          <p className="text-gray-500 max-w-md mx-auto mb-6 text-sm leading-relaxed">
            You haven't generated your AI-driven portfolio. We'll use your risk profile and our market predictions to recommend the best PSX stocks for you.
          </p>
          <Button onClick={() => navigate('/portfolio')} className="px-6">
            Generate Portfolio
          </Button>
        </div>
      ) : (
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <p>Portfolio data would go here.</p>
        </div>
      )}
    </div>
  );
};
