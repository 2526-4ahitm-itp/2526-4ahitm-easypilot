package com.example;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.emptyOrNullString;

@QuarkusTest
class StatusResourceTest {

    @Test
    void statusReturnsJsonWithUpState() {
        given()
            .when().get("/api/status")
            .then()
                .statusCode(200)
                .contentType("application/json")
                .body("name", is("easypilot-backend"))
                .body("status", is("UP"))
                .body("version", not(emptyOrNullString()));
    }

    @Test
    void versionComesFromConfiguredValue() {
        // application.properties pins easypilot.version=1.0-SNAPSHOT for this build.
        given()
            .when().get("/api/status")
            .then()
                .statusCode(200)
                .body("version", is("1.0-SNAPSHOT"));
    }
}
