angular.module('landing', [
    'ngRoute',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/landing/:landingPageName', {
            templateUrl: "landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    .controller("LandingPageCtrl", function ($scope,
                                             $http,
                                             $rootScope,
                                             $timeout) {

        console.log("i am the landing page ctrl")
        $scope.main = {}


        var animate = function(step){
            $scope.animation = step + "start"
            console.log("set animation", $scope.animation)
            $timeout(function(){
                $scope.animation = step + "finish"
                console.log("set animation", $scope.animation)
            }, 350)
        }


        var baseUrl = "https://api.oadoi.org/v1/publication/doi/"
        $scope.exampleDoi = "10.1016/j.tree.2007.03.007"
        $scope.exampleDoi = "10.1038/nature12373"

        $scope.selectExample = function(){
            $scope.main.exampleSelected = true
            $scope.main.doi = $scope.exampleDoi
        }
        $scope.tryAgain = function(){
            $scope.animation = null
            $scope.main = {}
        }

        


        $scope.$watch(function(s){return s.main.doi }, function(newVal, oldVal){
            console.log("doi change", newVal, oldVal)
            if (!newVal){
                return false
            }

            if (newVal.indexOf("10/") == 0 || newVal.indexOf("doi.org/10/") >= 0){
                $scope.main = {}
                "Sorry, we don't support ShortDOI yet."
                $rootScope.showAlert(
                    ga("send", "event", "input DOI", "shortDOI"  )
                )
                return true
            }


            if (newVal.indexOf("10.") >= 0) {
                animate(1)
                $http.get(baseUrl + newVal)
                    .success(function(resp){
                        console.log("got response back", resp.results[0])
                        if (newVal.indexOf($scope.exampleDoi) >= 0){
                            console.log("this is the sample DOI...waiting to return result.")
                            ga("send", "event", "input DOI", "sample DOI"  )

                            $timeout(function(){
                                console.log("returning the result now")
                                animate(2)
                                $scope.main.resp = resp.results[0]
                            }, 1000)
                        }
                        else {
                            animate(2)
                            ga("send", "event", "input DOI", "user-supplied DOI" )
                            $scope.main.resp = resp.results[0]
                        }


                    })
            }
            else {
                $scope.main = {}
                ga("send", "event", "input DOI", "typed the DOI"  )
                $rootScope.showAlert(
                    "Sorry, you have to paste DOIs here...you can't type them."
                )
            }
        })

    })










