const analyzeButton =
    document.getElementById("analyzeButton");

const filterSelect =
    document.getElementById("filter");

const maxImagesInput =
    document.getElementById("maxImages");

const statusText =
    document.getElementById("status");

const results =
    document.getElementById("results");

const summary =
    document.getElementById("summary");

const totalSuccessful =
    document.getElementById("totalSuccessful");

const usedFilter =
    document.getElementById("usedFilter");

const errorsCount =
    document.getElementById("errorsCount");

const errorsSection =
    document.getElementById("errorsSection");

const errorsContainer =
    document.getElementById("errors");


analyzeButton.addEventListener(
    "click",
    runAnalysis
);


async function runAnalysis() {

    const filterName = filterSelect.value;

    const maxImages =
        Number(maxImagesInput.value);


    if (
        maxImages < 1 ||
        maxImages > 20
    ) {
        alert(
            "Количество изображений должно быть от 1 до 20"
        );

        return;
    }


    analyzeButton.disabled = true;

    statusText.textContent =
        "Загрузка и обработка изображений...";

    results.innerHTML = "";

    errorsContainer.innerHTML = "";

    summary.classList.add("hidden");

    errorsSection.classList.add("hidden");


    try {

        const response =
            await fetch(
                "/api/analyze",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        filter_name: filterName,
                        max_images: maxImages
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            let message =
                "Ошибка выполнения анализа";

            if (data.detail) {
                message = data.detail;
            }

            throw new Error(message);
        }


        renderResponse(data);


        statusText.textContent =
            "Обработка завершена";


    } catch (error) {

        console.error(error);

        statusText.textContent =
            `Ошибка: ${error.message}`;

    } finally {

        analyzeButton.disabled = false;
    }
}


function renderResponse(data) {

    summary.classList.remove("hidden");

    totalSuccessful.textContent =
        data.total_successful;

    usedFilter.textContent =
        data.filter_requested;

    errorsCount.textContent =
        data.errors.length;


    data.images.forEach(
        (image, index) => {

            const card =
                createImageCard(
                    image,
                    index
                );

            results.appendChild(card);
        }
    );


    if (data.errors.length > 0) {

        errorsSection.classList.remove(
            "hidden"
        );

        renderErrors(data.errors);
    }
}


function createImageCard(
    image,
    index
) {

    const card =
        document.createElement("article");

    card.className = "image-card";


    const rgb =
        image.stats.avg_color_rgb;

    const rgbText =
        `${rgb[0]}, ${rgb[1]}, ${rgb[2]}`;

    const rgbCss =
        `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;


    card.innerHTML = `
        <h2>
            Изображение ${index + 1}
        </h2>

        <div class="images">

            <div class="image-box">

                <span>
                    ДО
                </span>

                <img
                    src="${image.original_base64}"
                    alt="Исходное изображение"
                >

            </div>


            <div class="image-box">

                <span>
                    ПОСЛЕ
                </span>

                <img
                    src="${image.processed_base64}"
                    alt="Обработанное изображение"
                >

            </div>

        </div>


        <div class="stats">

            <div class="stat">
                <span>Размер</span>

                <strong>
                    ${image.stats.width}
                    ×
                    ${image.stats.height}
                </strong>
            </div>


            <div class="stat">
                <span>
                    Соотношение сторон
                </span>

                <strong>
                    ${image.stats.aspect_ratio}
                </strong>
            </div>


            <div class="stat">
                <span>
                    Средняя яркость
                </span>

                <strong>
                    ${image.stats.mean_brightness}
                </strong>
            </div>


            <div class="stat">
                <span>
                    Контраст
                </span>

                <strong>
                    ${image.stats.contrast}
                </strong>
            </div>


            <div class="stat">

                <span>
                    Средний RGB
                </span>

                <div class="color-row">

                    <div
                        class="color-preview"
                        style="
                            background:
                            ${rgbCss};
                        "
                    ></div>

                    <strong>
                        ${rgbText}
                    </strong>

                </div>

            </div>

        </div>


        <div class="filters">

            <strong>
                Применённые фильтры:
            </strong>

            ${image.filters_applied.join(", ")}

        </div>
    `;


    return card;
}


function renderErrors(errors) {

    errorsContainer.innerHTML = "";


    errors.forEach(error => {

        const element =
            document.createElement("div");

        element.className =
            "error-item";


        element.innerHTML = `
            <strong>
                ${error.url || "Неизвестный URL"}
            </strong>

            <br>

            ${error.error}
        `;


        errorsContainer.appendChild(
            element
        );
    });
}