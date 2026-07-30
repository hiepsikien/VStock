import 'react-native-gesture-handler';
import { registerRootComponent } from 'expo';

import { initSentry } from './src/sentry';
import './src/tasks/priceAlertBackgroundTask';
import App from './App';

initSentry();

registerRootComponent(App);
