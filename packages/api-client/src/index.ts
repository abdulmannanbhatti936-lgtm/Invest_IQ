export * from './client';
export * from './auth';

export const healthCheck = async () => {
  const res = await fetch('http://127.0.0.1:8000/health');
  return res.json();
};
