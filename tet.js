import { FreeApp, UIPlane, UIText } from 'freejs';

// Инициализация приложения Free.js
const app = new FreeApp({ container: document.body, background: 0x4b0082 });

// Создание контейнера для заголовка
const headerContainer = new UIPlane({
    width: 10,
    height: 2,
    position: { x: 0, y: 4, z: -10 },
    backgroundColor: 0x191970,
    borderRadius: 0.2,
});

// Добавление логотипа в заголовок
const logo = new UIPlane({
    width: 2,
    height: 1,
    texture: 'static/img/love.png',
    position: { x: -4, y: 0, z: 0.1 },
});
headerContainer.add(logo);

// Создание баланса
const balanceText = new UIText({
    text: 'Баланс: 100 DCT',
    color: '#ffffff',
    fontSize: 0.5,
    position: { x: 2, y: 0, z: 0.1 },
});
headerContainer.add(balanceText);

// Добавление контейнера на сцену
app.scene.add(headerContainer);

// Запуск приложения
app.start();
