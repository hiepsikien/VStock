module.exports = function (api) {
  api.cache(true);
  return {
    // babel-preset-expo SDK 58 auto-adds react-native-worklets/plugin when installed.
    presets: ['babel-preset-expo'],
  };
};
