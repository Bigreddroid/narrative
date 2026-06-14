import { useEffect, useRef } from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { Text, StyleSheet, useColorScheme } from "react-native";

import { getThemeColors } from "./lib/colors.js";
import { registerForPushNotifications, addNotificationNavigationListener } from "./lib/notifications.js";

import AuthScreen from "./screens/AuthScreen.jsx";
import HomeScreen from "./screens/HomeScreen.jsx";
import WorldMapScreen from "./screens/WorldMapScreen.jsx";
import EventScreen from "./screens/EventScreen.jsx";
import SearchScreen from "./screens/SearchScreen.jsx";
import ProfileScreen from "./screens/ProfileScreen.jsx";

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

// Unicode approximations of SF Symbol icons used in mockups
const TAB_ICONS = {
  Home:    "⌂",
  World:   "◉",
  Search:  "⊕",
  Profile: "◎",
};

function TabIcon({ name, focused, colors }) {
  return (
    <Text style={[styles.tabIcon, { color: focused ? colors.tabActive : colors.tabInactive }]}>
      {TAB_ICONS[name] || "·"}
    </Text>
  );
}

function MainTabs({ colors }) {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.tabBar,
          borderTopColor: colors.border,
          height: 64,
          paddingBottom: 10,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "600",
          letterSpacing: 0.3,
        },
        tabBarActiveTintColor: colors.tabActive,
        tabBarInactiveTintColor: colors.tabInactive,
        tabBarIcon: ({ focused }) => <TabIcon name={route.name} focused={focused} colors={colors} />,
      })}
    >
      <Tab.Screen name="Home"    component={HomeScreen} />
      <Tab.Screen name="World"   component={WorldMapScreen} />
      <Tab.Screen name="Search"  component={SearchScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  const navigationRef = useRef(null);
  const scheme = useColorScheme();
  const isDark = scheme === "dark";
  const colors = getThemeColors(isDark);

  const NAV_THEME = {
    ...DefaultTheme,
    colors: {
      ...DefaultTheme.colors,
      background: colors.bgBase,
      card: colors.bgSurface,
      text: colors.textPrimary,
      border: colors.border,
      primary: colors.accent,
    },
  };

  useEffect(() => {
    registerForPushNotifications();
    const sub = addNotificationNavigationListener(navigationRef);
    return () => sub?.remove();
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <NavigationContainer ref={navigationRef} theme={NAV_THEME}>
        <StatusBar style={isDark ? "light" : "dark"} />
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Auth" component={AuthScreen} />
          <Stack.Screen name="Main">
            {() => <MainTabs colors={colors} />}
          </Stack.Screen>
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
