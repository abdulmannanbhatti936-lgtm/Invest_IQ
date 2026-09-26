import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { stocksApi } from '@investiq/api-client';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, 
  ResponsiveContainer, ReferenceArea 
} from 'recharts';
import { ArrowLeft, TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

// Mock chart format
const formatChartData = (history: any[], prediction: any) => {
  if (!history) return [];
  const data = history.map(h => ({
    date: new Date(h.timestamp).toLocaleDateString(),
    price: h.close,
    isPrediction: false
  }));

  // Add prediction point at the end if it exists
  if (prediction && data.length > 0) {
    const lastDate = new Date(history[history.length - 1].timestamp);
    const nextDate = new Date(lastDate);
    nextDate.setDate(nextDate.getDate() + 1);
    
    data.push({
      date: nextDate.toLocaleDateString(),
      price: prediction.predicted_price,
      isPrediction: true
    });
  }
  return data;
};

export const StockDetail = () => {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();

  const { data: quote, isLoading: isQuoteLoading } = useQuery({
    queryKey: ['stockQuote', ticker],
    queryFn: () => stocksApi.getQuote(ticker!),
    enabled: !!ticker,
  });

  const { data: history, isLoading: isHistoryLoading } = useQuery({
    queryKey: ['stockHistory', ticker],
    queryFn: () => stocksApi.getHistory(ticker!, '1y'),
    enabled: !!ticker,
  });

  const { data: prediction } = useQuery({
    queryKey: ['stockPrediction', ticker],
    queryFn: () => stocksApi.getPrediction(ticker!),
    enabled: !!ticker,
    retry: false // It might 404 if no prediction is ready
  });

  if (isQuoteLoading) {
    return <div className="p-8 text-center text-gray-500">Loading stock details...</div>;
  }

  if (!quote) {
    return (
      <div className="p-8 max-w-3xl mx-auto text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Stock not found</h2>
        <Button onClick={() => navigate('/stocks')}>Back to Search</Button>
      </div>
    );
  }

  const change = quote.current_price - quote.previous_close;
  const changePercent = (change / quote.previous_close) * 100;
  const isPositive = change > 0;
  const isNegative = change < 0;

  const chartData = formatChartData(history || [], prediction);
  
  // Custom tooltip for chart to differentiate predicted vs actual
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      return (
        <div className="bg-white p-3 border border-gray-100 shadow-lg rounded-lg">
          <p className="font-semibold text-gray-900">{label}</p>
          <p className={dataPoint.isPrediction ? "text-purple-600 font-bold" : "text-gray-700"}>
            Price: Rs. {payload[0].value.toFixed(2)}
            {dataPoint.isPrediction && " (AI Forecast)"}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Breadcrumb / Back Navigation */}
      <button 
        onClick={() => navigate('/stocks')}
        className="flex items-center text-sm text-gray-500 hover:text-gray-900 transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-1" /> Back to Search
      </button>

      {/* Header section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{quote.ticker}</h1>
          <p className="text-lg text-gray-500">{quote.name}</p>
          {quote.sector && <p className="text-sm text-gray-400 mt-1">{quote.sector}</p>}
        </div>
        
        <div className="text-left md:text-right">
          <p className="text-3xl font-mono font-bold">Rs. {quote.current_price.toFixed(2)}</p>
          <p className={`text-lg font-medium flex items-center md:justify-end ${
            isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-500'
          }`}>
            {isPositive && <TrendingUp className="w-5 h-5 mr-1" />}
            {isNegative && <TrendingDown className="w-5 h-5 mr-1" />}
            {!isPositive && !isNegative && <Minus className="w-5 h-5 mr-1" />}
            {change > 0 ? '+' : ''}{change.toFixed(2)} ({changePercent.toFixed(2)}%)
          </p>
        </div>
      </div>

      {/* AI Prediction Section */}
      <Card className="bg-blue-50/50 border-blue-100">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-gray-900">AI Forecast</h3>
                {prediction && (
                  <Badge variant={
                    prediction.signal === 'BUY' ? 'success' : 
                    prediction.signal === 'SELL' ? 'danger' : 'neutral'
                  }>
                    {prediction.signal} Signal
                  </Badge>
                )}
              </div>
              <p className="text-sm text-gray-600">
                Based on historical trends, technical indicators, and market sentiment.
              </p>
            </div>
            
            {prediction ? (
              <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-100 text-center min-w-[200px]">
                <p className="text-sm text-gray-500 mb-1">Target Price (Next Day)</p>
                <p className="text-2xl font-bold text-gray-900">
                  Rs. {prediction.predicted_price.toFixed(2)}
                </p>
                
                <div className="mt-3 pt-3 border-t border-gray-50 flex flex-col items-center gap-1">
                  <div className="flex items-center justify-between w-full text-xs">
                    <span className="text-gray-500">Confidence</span>
                    <span className="font-medium">{(prediction.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                  {/* Confidence meter */}
                  <div className="w-full bg-gray-100 rounded-full h-1.5 mt-1 overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        prediction.confidence_score > 0.7 ? 'bg-green-500' :
                        prediction.confidence_score > 0.4 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${prediction.confidence_score * 100}%` }}
                    />
                  </div>
                  {prediction.confidence_score < 0.5 && (
                    <p className="text-xs text-yellow-600 mt-2 flex items-start gap-1 text-left">
                      <Info className="w-3 h-3 mt-0.5 shrink-0" />
                      Low confidence: Market conditions are highly volatile or signals conflict.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg p-4 text-center text-sm text-gray-500 border border-dashed border-gray-200">
                No prediction available for this ticker yet.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Chart Section */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Price History & Forecast</CardTitle>
            <p className="text-sm text-gray-500 font-medium">
              {isPositive ? `Up ${changePercent.toFixed(1)}%` : `Down ${Math.abs(changePercent).toFixed(1)}%`} recently
            </p>
          </div>
        </CardHeader>
        <CardContent>
          {isHistoryLoading ? (
            <div className="h-[400px] flex items-center justify-center text-gray-400">Loading chart data...</div>
          ) : chartData.length > 0 ? (
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                  <XAxis 
                    dataKey="date" 
                    tick={{fontSize: 12}} 
                    tickMargin={10} 
                    minTickGap={30}
                    stroke="#9ca3af"
                  />
                  <YAxis 
                    domain={['auto', 'auto']}
                    tick={{fontSize: 12}} 
                    tickFormatter={(val) => `Rs ${val}`}
                    stroke="#9ca3af"
                    width={80}
                  />
                  <RechartsTooltip content={<CustomTooltip />} />
                  
                  {/* Actual Price Line */}
                  <Line 
                    type="monotone" 
                    dataKey="price" 
                    stroke="#2563eb" 
                    strokeWidth={2} 
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                  
                  {/* Highlight the prediction area if prediction exists */}
                  {prediction && chartData.length > 1 && (
                    <ReferenceArea 
                      x1={chartData[chartData.length - 2].date}
                      x2={chartData[chartData.length - 1].date}
                      fill="#f3e8ff" 
                      fillOpacity={0.5}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[400px] flex items-center justify-center text-gray-400">
              No historical data available.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Key Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-gray-500 mb-1">Open</p>
            <p className="font-mono text-lg font-medium">Rs. {quote.open.toFixed(2)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-gray-500 mb-1">High</p>
            <p className="font-mono text-lg font-medium">Rs. {quote.high.toFixed(2)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-gray-500 mb-1">Low</p>
            <p className="font-mono text-lg font-medium">Rs. {quote.low.toFixed(2)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-gray-500 mb-1">Volume</p>
            <p className="font-mono text-lg font-medium">
              {quote.volume > 1000000 
                ? `${(quote.volume / 1000000).toFixed(2)}M` 
                : quote.volume > 1000 
                ? `${(quote.volume / 1000).toFixed(2)}K` 
                : quote.volume}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Footer Disclaimer */}
      <div className="mt-12 p-4 bg-gray-50 rounded-lg border border-gray-100">
        <p className="text-sm text-gray-500 text-center">
          <strong>Advisory only.</strong> Not a licensed financial advisor. Predictions are probabilistic. Execute trades only through a licensed PSX broker.
        </p>
      </div>
    </div>
  );
};
