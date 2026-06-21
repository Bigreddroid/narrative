import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { api } from "./api.js";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications() {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("alerts", {
      name: "Event alerts",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: "#F5A623",
    });
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== "granted") return null;

  const token = (await Notifications.getExpoPushTokenAsync()).data;

  // Register with backend
  try {
    await api.post("/notifications/register", { fcm_token: token, platform: Platform.OS });
  } catch (err) {
    console.warn("Failed to register push token:", err.message);
  }

  return token;
}

export function useNotificationNavigation(navigationRef) {
  // Handle notification tap when app is backgrounded/killed
  Notifications.addNotificationResponseReceivedListener((response) => {
    const data = response.notification.request.content.data;
    if (data?.event_id && navigationRef?.current?.isReady?.()) {
      navigationRef.current.navigate("Event", { eventId: data.event_id });
    }
  });
}
