module Data.InputsTest exposing (..)

import Data.Country as Country
import Data.Inputs as Inputs exposing (tShirtCotonAsie)
import Expect
import List.Extra as LE
import Test exposing (..)
import TestUtils exposing (asTest, suiteWithDb)


sampleQuery : Inputs.Query
sampleQuery =
    Inputs.jupeCircuitAsie


suite : Test
suite =
    suiteWithDb "Data.Inputs"
        (\db ->
            [ describe "Base64"
                [ describe "Encoding and decoding queries"
                    [ sampleQuery
                        |> Inputs.fromQuery db
                        |> Result.map Inputs.toQuery
                        |> Expect.equal (Ok sampleQuery)
                        |> asTest "should encode and decode a query"
                    ]
                , describe "Base64 encoding and decoding queries"
                    [ sampleQuery
                        |> Inputs.b64encode
                        |> Inputs.b64decode
                        |> Expect.equal (Ok sampleQuery)
                        |> asTest "should base64 encode and decode a query"
                    ]
                ]
            , describe "Query countries validation"
                [ { tShirtCotonAsie
                    | countryFabric = Country.Code "CN"
                    , countryDyeing = Country.Code "CN"
                    , countryMaking = Country.Code "CN"
                  }
                    |> Inputs.fromQuery db
                    |> Result.map Inputs.countryList
                    |> Result.andThen (LE.getAt 0 >> Maybe.map .code >> Result.fromMaybe "")
                    |> Expect.equal (Ok (Country.codeFromString "CN"))
                    |> asTest "should replace the first country with the material's default country"
                , { tShirtCotonAsie
                    | countryFabric = Country.Code "XX"
                    , countryDyeing = Country.Code "CN"
                    , countryMaking = Country.Code "CN"
                  }
                    |> Inputs.fromQuery db
                    |> Expect.equal (Err "Code pays invalide: XX.")
                    |> asTest "should validate country codes"
                ]
            ]
        )
