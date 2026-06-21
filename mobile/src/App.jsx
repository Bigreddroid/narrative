import { useEffect, useRef } from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { Text, StyleSheet } from "react-native";

import { COLORS } from "./lib/colors.js";
import { registerForPushNotifications, useNotificationNavigation } from "./lib/notifications.js";

import AuthScreen from "./screens/AuthScreen.jsx";
import WorldMapScreen from "./screens/WorldMapScreen.jsx";
import EventScreen from "./screens/EventScreen.jsx";
import FollowingScreen from "./screens/FollowingScreen.jsx";
import SearchScreen from "./screens/SearchScreen.jsx";
import ProfileScreen from "./screens/ProfileScreen.jsx";

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

const NAV_THEME = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: COLORS.bgBase,
    card: COLORS.bgSurface,
    text: COLORS.textPrimary,
    border: COLORS.border,
    primary: COLORS.accent,
  },
};

const TAB_ICONS = {
  World: "◉",
  Following: "★",
  Search: "⊕",
  Profile: "◎",
};

function TabIcon({ name, focused }) {
  return (
    <Text style={[styles.tabIcon, { color: focused ? COLORS.accent : COLORS.textMuted }]}>
      {TAB_ICONS[name] || "·"}
    </Text>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: COLORS.bgSurface,
          borderTopColor: COLORS.border,
          height: 64,
          paddingBottom: 10,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "600",
          letterSpacing: 0.3,
        },
        tabBarActiveTintColor: COLORS.accent,
        tabBarInactiveTintColor: COLORS.textMuted,
        tabBarIcon: ({ focused }) => <TabIcon name={route.name} focused={focused} />,
      })}
    >
      <Tab.Screen name="World" component={WorldMapScreen} />
      <Tab.Screen name="Following" component={FollowingScreen} />
      <Tab.Screen name="Search" component={SearchScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  const navigationRef = useRef(null);

  useEffect(() => {
    registerForPushNotifications();
    useNotificationNavigation(navigationRef);
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <NavigationContainer ref={navigationRef} theme={NAV_THEME}>
        <StatusBar style="light" />
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Auth" component={AuthScreen} />
          <Stack.Screen name="Main" component={MainTabs} />
          <Stack.Screen
            name="Event"
            component={EventScreen}
            options={{
              headerShown: false,
              presentation: "card",
              animationTypeForReplace: "push",
            }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  tabIcon: { fontSize: 18 },
});
