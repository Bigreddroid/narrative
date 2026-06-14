const { getDefaultConfig } = require("expo/metro-config");
const { withSkiaMetroConfig } = require("@shopify/react-native-skia/metro");

const config = getDefaultConfig(__dirname);
module.exports = withSkiaMetroConfig(config);
