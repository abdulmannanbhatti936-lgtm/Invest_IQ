import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { stocksApi } from '@investiq/api-client';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';

export const Stocks = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 500);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  const { data: searchResults, isLoading } = useQuery({
    queryKey: ['stocksSearch', debouncedQuery],
    queryFn: () => stocksApi.search(debouncedQuery),
    enabled: debouncedQuery.length > 0,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setDebouncedQuery(searchQuery);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Market Overview</h1>
          <p className="text-sm text-gray-500">Search and analyze Pakistan Stock Exchange (PSX) companies.</p>
        </div>
        
        <form onSubmit={handleSearch} className="w-full md:w-96 flex gap-2">
          <Input
            label="Search"
            type="text"
            placeholder="Search by ticker (e.g. SYS, ENGRO)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 mt-0"
          />
          <Button type="submit" aria-label="Search">
            <Search className="w-5 h-5" />
          </Button>
        </form>
      </div>

      <div className="space-y-4">
        {isLoading && <div className="text-center py-8 text-gray-500">Loading results...</div>}
        
        {!isLoading && debouncedQuery.length > 0 && searchResults?.results.length === 0 && (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-100 shadow-sm">
            <p className="text-gray-500">No stocks found matching "{debouncedQuery}"</p>
          </div>
        )}

        {!isLoading && searchResults?.results && searchResults.results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {searchResults.results.map((stock) => {
              const change = stock.current_price - stock.previous_close;
              const changePercent = (change / stock.previous_close) * 100;
              const isPositive = change > 0;
              const isNegative = change < 0;

              return (
                <Card 
                  key={stock.ticker} 
                  className="cursor-pointer hover:border-blue-300 transition-colors"
                  onClick={() => navigate(`/stocks/${stock.ticker}`)}
                >
                  <CardContent className="p-0">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-bold text-lg">{stock.ticker}</h3>
                        <p className="text-xs text-gray-500 truncate max-w-[150px]" title={stock.name}>
                          {stock.name}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-mono text-lg font-semibold">Rs. {stock.current_price.toFixed(2)}</p>
                        <p className={`text-sm font-medium flex items-center justify-end ${
                          isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-500'
                        }`}>
                          {isPositive && <TrendingUp className="w-4 h-4 mr-1" />}
                          {isNegative && <TrendingDown className="w-4 h-4 mr-1" />}
                          {!isPositive && !isNegative && <Minus className="w-4 h-4 mr-1" />}
                          {change > 0 ? '+' : ''}{change.toFixed(2)} ({changePercent.toFixed(2)}%)
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
