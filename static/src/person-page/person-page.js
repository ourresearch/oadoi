angular.module('personPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/:tab?', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            reloadOnSearch: false,
            resolve: {
                personResp: function($http, $route, Person){
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){



        $scope.global.title = Person.d.given_names + " " + Person.d.family_name
        $scope.person = Person.d
        $scope.products = Person.d.products
        $scope.sources = Person.d.sources
        $scope.badges = Person.d.badges



        console.log("retrieved the person", $scope.person)

        $scope.profileStatus = "all_good"
        $scope.tab =  $routeParams.tab || "overview"

        //if (!Person.d.email) {
        //    $scope.userForm = {}
        //    $scope.profileStatus = "no_email"
        //}
        //else if (!Person.d.products) {
        //    $scope.profileStatus = "no_products"
        //}
        //else {
        //    $scope.profileStatus = "all_good"
        //}

        $scope.settingEmail = false
        $scope.submitEmail = function(){
            console.log("setting the email!", $scope.userForm.email)
            $scope.settingEmail = true
            $http.post("/api/me", {email: $scope.userForm.email})
                .success(function(resp){
                    $scope.settingEmail = false
                    $route.reload()
                })
        }





        $scope.badgeLimit = 3
        $scope.numBadgesToShow = 3
        $scope.toggleBadges = function(){
            if ($scope.numBadgesToShow == 3) {
                $scope.numBadgesToShow = 9999999999
            }
            else {
                $scope.numBadgesToShow = 3
            }
        }


        // posts stuff
        $scope.posts = []
        _.each(Person.d.products, function(product){
            var myDoi = product.doi
            var myTitle = product.title
            _.each(product.posts, function(myPost){
                myPost.citesDoi = myDoi
                myPost.citesTitle = myTitle
                $scope.posts.push(myPost)
            })
        })

        // get the tweeters.
        var uniqueTweeters = {}
        _.each(Person.d.products, function(product){
            _.each(product.tweeters, function(tweeter){
                uniqueTweeters[tweeter.url] = tweeter
            })
        })
        $scope.tweeters = _.values(uniqueTweeters)

        $scope.postsSum = 0
        _.each(Person.d.sources, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.selectedChannel = undefined
        $scope.setSelectedChannel= function(channel){
            console.log("channel click", channel)
            $scope.selectedChannel = channel

            if ($routeParams.tab != 'mentions') {
                $location.url("u/" + Person.d.orcid_id + "/mentions?filter=" + channel)
            }
        }
        // stuff for the mentions tab only
        if ($routeParams.tab == "mentions"){
            if ($location.search().filter){
                var channelName = $location.search().filter
                var myChannel = _.find(Person.d.sources, function(v){
                    return v.source_name = myChannelName
                })
                $scope.setSelectedChannel(myChannel)
                $location.search({filter: null})
            }
            else {
                $scope.setSelectedChannel(undefined)
            }
        }


        // genre stuff
        var genreGroups = _.groupBy(Person.d.products, "genre")
        var genres = []
        _.each(genreGroups, function(v, k){
            genres.push({
                name: k,
                count: v.length
            })
        })
        console.log("genres", genres)

        $scope.genres = genres
        $scope.selectedGenre = undefined
        $scope.setSelectedGenre = function(genre){
            console.log("click", genre)
            $scope.selectedGenre = genre
        }





        // dialog stuff
        $scope.personScoreModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title('The online impact score')
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                //.targetEvent(ev)
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("learn more")
                $location.path("about/metrics")
            }, function() {
                console.log("ok")
            });
        };


        $scope.tIndexModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title("t-index")
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };


        $scope.impressionsModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title("Twitter impressions")
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };






    })



