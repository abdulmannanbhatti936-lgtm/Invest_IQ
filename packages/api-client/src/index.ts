import { apiClient } from './client';

export * from './client';
export * from './auth';
export * from './stocks';

export const healthCheck = async (): Promise<{ status: string }> => {
  const { data } = await apiClient.get<{ status: string }>('/health');
  return data;
};
