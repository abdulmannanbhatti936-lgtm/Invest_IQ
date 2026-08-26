import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, View } from 'react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { healthCheck } from '@investiq/api-client';
import type { Placeholder } from '@investiq/shared-types';
import { colors } from '@investiq/design-tokens';
import i18next from '@investiq/i18n';

const Tab = createBottomTabNavigator();
const queryClient = new QueryClient();

function PlaceholderScreen({ route }: any) {
  const [healthStatus, setHealthStatus] = useState<string>('Loading backend status...');

  useEffect(() => {
    healthCheck()
      .then((res: any) => setHealthStatus(JSON.stringify(res)))
      .catch((err: any) => setHealthStatus('Error: ' + err.message));
  }, []);

  return (
    <View
      style={{
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.background,
      }}
    >
      <Text style={{ fontSize: 24, fontWeight: 'bold', color: colors.primary }}>{route.name}</Text>
      <Text style={{ marginTop: 10 }}>{i18next.t('test_key')} (from i18n)</Text>
      <Text style={{ marginTop: 20, color: '#666' }}>Backend status: {healthStatus}</Text>
    </View>
  );
}

export default function App() {
  const _testType: Placeholder = { id: 'mobile-test' };
  console.log(_testType);

  return (
    <QueryClientProvider client={queryClient}>
      <NavigationContainer>
        <Tab.Navigator>
          <Tab.Screen name="Home" component={PlaceholderScreen} />
          <Tab.Screen name="Stocks" component={PlaceholderScreen} />
          <Tab.Screen name="Portfolio" component={PlaceholderScreen} />
          <Tab.Screen name="Chat" component={PlaceholderScreen} />
          <Tab.Screen name="Notifications" component={PlaceholderScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </QueryClientProvider>
  );
}
